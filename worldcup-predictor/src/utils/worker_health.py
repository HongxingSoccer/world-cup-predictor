"""Tiny HTTP `/healthz` server for Celery workers running under K8s.

Celery itself doesn't expose an HTTP endpoint; K8s livenessProbe /
readinessProbe needs one. Rather than ship a sidecar, we start a small
aiohttp app on a background thread in the same process whenever the
``WORKER_HEALTH_SERVER`` env var is truthy. Local docker-compose
doesn't set the var, so the existing dev flow is unchanged.

Probe semantics:
* ``/healthz`` — liveness. Returns 200 as long as the Python process is
  alive. Failing it should trigger a pod restart.
* ``/readyz`` — readiness. Returns 200 only when the Celery broker
  (Redis) is reachable. Failing it should take the pod out of any
  workload distributor (not that K8s does much with worker readiness,
  but it's the conventional split + lets you wire HPA on it).

The server runs on 0.0.0.0:WORKER_HEALTH_PORT (default 8001) — distinct
from the FastAPI 8000 so the ml-api can in principle expose both
side-by-side later.
"""
from __future__ import annotations

import asyncio
import os
import threading
from typing import Optional

import structlog
from aiohttp import web

logger = structlog.get_logger(__name__)

_DEFAULT_PORT = 8001


def _truthy(raw: Optional[str]) -> bool:
    if raw is None:
        return False
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _broker_reachable() -> bool:
    """Best-effort liveness check for the Celery broker (Redis)."""
    try:
        import redis

        from src.config.settings import settings

        client = redis.Redis.from_url(
            settings.REDIS_URL,
            socket_connect_timeout=2.0,
            socket_timeout=2.0,
        )
        return bool(client.ping())
    except Exception as exc:  # pragma: no cover — exercised in deployment
        logger.debug("worker_readyz_broker_unreachable", error=str(exc))
        return False


async def _healthz(_request: web.Request) -> web.Response:
    return web.json_response({"status": "ok"})


async def _readyz(_request: web.Request) -> web.Response:
    if _broker_reachable():
        return web.json_response({"status": "ready"})
    return web.json_response({"status": "broker_unreachable"}, status=503)


def _build_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/healthz", _healthz)
    app.router.add_get("/readyz", _readyz)
    return app


def _run(port: int) -> None:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        runner = web.AppRunner(_build_app())
        loop.run_until_complete(runner.setup())
        site = web.TCPSite(runner, host="0.0.0.0", port=port)
        loop.run_until_complete(site.start())
        logger.info("worker_health_server_started", port=port)
        loop.run_forever()
    except Exception as exc:  # pragma: no cover — defensive
        logger.error("worker_health_server_crashed", error=str(exc))


def maybe_start_health_server() -> None:
    """Start the health server in a daemon thread if WORKER_HEALTH_SERVER is set.

    Idempotent + safe to call from celery_app module import time:
    workers reading the env var see "1"/"true"/"yes" and spin up the
    server once. Anything else (including no var at all) is a no-op,
    keeping local docker-compose unchanged.
    """
    if not _truthy(os.environ.get("WORKER_HEALTH_SERVER")):
        return
    if getattr(maybe_start_health_server, "_started", False):
        return
    port = int(os.environ.get("WORKER_HEALTH_PORT", _DEFAULT_PORT))
    thread = threading.Thread(
        target=_run,
        kwargs={"port": port},
        daemon=True,
        name="wcp-worker-health",
    )
    thread.start()
    maybe_start_health_server._started = True  # type: ignore[attr-defined]

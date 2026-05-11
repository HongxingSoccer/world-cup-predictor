"""Celery worker entrypoint.

Importing this module triggers two things in order:

    1. Loads the configured Celery `app` from `src.config.celery_config`.
    2. Imports `src.tasks` so every `@app.task` decorator runs and registers
       its task in the global registry.

Workers / beat are started via:

    celery -A src.celery_app worker --loglevel=INFO
    celery -A src.celery_app beat   --loglevel=INFO

Pointing at this thin re-export module (rather than the config module
directly) ensures the task registry is fully populated before the worker
starts consuming, which avoids "Received unregistered task" errors on the
first message.
"""
from __future__ import annotations

# Side-effect import — registers every @app.task in src/tasks/*.
# Marked noqa because flake8 / ruff would otherwise flag the unused import.
import src.tasks  # noqa: F401
from src.config.celery_config import app

# Optional: when the worker is running under K8s the deployment sets
# WORKER_HEALTH_SERVER=true so /healthz + /readyz become reachable on
# port 8001 for liveness / readiness probes. The function is a no-op
# when the env var is unset (local docker-compose default).
from src.utils.worker_health import maybe_start_health_server

maybe_start_health_server()

__all__ = ["app"]

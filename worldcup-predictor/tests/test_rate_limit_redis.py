"""Tests for the Redis-backed sliding-window rate limiter.

Uses ``fakeredis`` so the suite stays hermetic — no real Redis needed in CI.
"""
from __future__ import annotations

import time

import fakeredis
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.middleware import RateLimitMiddleware
from src.api.rate_limit_redis import KEY_PREFIX, RedisSlidingWindowLimiter


def _build_limiter(budget: int, window_seconds: int = 60):
    """Fresh fakeredis-backed limiter per test, isolated keyspace."""
    client = fakeredis.FakeRedis(decode_responses=True)
    return client, RedisSlidingWindowLimiter(
        client, budget=budget, window_seconds=window_seconds
    )


def test_allows_within_budget():
    _client, limiter = _build_limiter(budget=3)
    for i in range(3):
        assert limiter.allow("1.2.3.4") is True, f"call {i} should be allowed"


def test_blocks_over_budget():
    _client, limiter = _build_limiter(budget=2)
    assert limiter.allow("1.2.3.4") is True
    assert limiter.allow("1.2.3.4") is True
    # Third call inside the window must be rejected.
    assert limiter.allow("1.2.3.4") is False


def test_isolates_per_ip():
    """One IP burning their budget must not affect another IP."""
    _client, limiter = _build_limiter(budget=1)
    assert limiter.allow("a.a.a.a") is True
    # second from same IP is rejected
    assert limiter.allow("a.a.a.a") is False
    # different IP: fresh budget
    assert limiter.allow("b.b.b.b") is True


def test_window_slides_old_hits_expire(monkeypatch):
    """Hits older than the window must be evicted on the next request."""
    _client, limiter = _build_limiter(budget=2, window_seconds=1)
    assert limiter.allow("1.2.3.4") is True
    assert limiter.allow("1.2.3.4") is True
    # Past the window — eviction sweep clears the two old hits.
    time.sleep(1.1)
    assert limiter.allow("1.2.3.4") is True


def test_zset_size_tracks_active_window():
    """ZCARD should reflect the within-window hit count after each request."""
    client, limiter = _build_limiter(budget=5)
    limiter.allow("1.2.3.4")
    limiter.allow("1.2.3.4")
    assert client.zcard(f"{KEY_PREFIX}1.2.3.4") == 2


def test_redis_unavailable_fails_open():
    """When the pipeline raises, the request must be allowed through."""

    class _ExplodingClient:
        def pipeline(self, transaction=False):  # type: ignore[no-untyped-def]
            raise RuntimeError("redis down")

    limiter = RedisSlidingWindowLimiter(
        _ExplodingClient(),  # type: ignore[arg-type]
        budget=1,
        window_seconds=60,
    )
    # First request would normally consume the budget; second would normally
    # be blocked. Because pipeline() raises, *both* must be allowed.
    assert limiter.allow("1.2.3.4") is True
    assert limiter.allow("1.2.3.4") is True


# ---------------------------------------------------------------------------
# Middleware-level integration: assemble a tiny FastAPI app + TestClient and
# verify the limiter actually returns 429 over the wire.
# ---------------------------------------------------------------------------


def _build_app(limiter: RedisSlidingWindowLimiter, budget: int) -> FastAPI:
    app = FastAPI()
    app.add_middleware(
        RateLimitMiddleware,
        requests_per_minute=budget,
        redis_limiter=limiter,
    )

    @app.get("/echo")
    def _echo() -> dict:
        return {"ok": True}

    return app


def test_middleware_returns_429_after_budget():
    _client, limiter = _build_limiter(budget=2)
    app = _build_app(limiter, budget=2)
    client = TestClient(app)

    assert client.get("/echo").status_code == 200
    assert client.get("/echo").status_code == 200
    rsp = client.get("/echo")
    assert rsp.status_code == 429
    body = rsp.json()
    assert body["error"] == "RATE_LIMITED"


def test_middleware_skips_public_paths(monkeypatch):
    """Public paths (e.g. /health) must never count against the budget."""
    _client, limiter = _build_limiter(budget=1)
    # Build a stand-in FastAPI exposing a public path the middleware whitelists.
    app = FastAPI()
    app.add_middleware(
        RateLimitMiddleware,
        requests_per_minute=1,
        redis_limiter=limiter,
    )

    @app.get("/health")
    def _health() -> dict:
        return {"status": "ok"}

    client = TestClient(app)
    # 10 hits to a public path; budget would have been 1 for a private path.
    for _ in range(10):
        assert client.get("/health").status_code == 200


def test_middleware_fail_open_when_limiter_explodes():
    """If the Redis limiter blows up, the middleware must not 500 the request."""

    class _ExplodingClient:
        def pipeline(self, transaction=False):  # type: ignore[no-untyped-def]
            raise RuntimeError("redis down")

    limiter = RedisSlidingWindowLimiter(
        _ExplodingClient(),  # type: ignore[arg-type]
        budget=1,
        window_seconds=60,
    )
    app = _build_app(limiter, budget=1)
    client = TestClient(app)
    for _ in range(5):
        assert client.get("/echo").status_code == 200

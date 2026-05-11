"""Redis-backed sliding-window rate limiter.

Replaces the in-process LRU sliding-window counter in ``middleware.py`` so
the limit stays consistent across multiple FastAPI replicas (EKS / ECS).
The in-process implementation only sees its own pod's traffic, so under
N replicas each client effectively gets N× the configured budget.

Algorithm:

    pipeline:
        ZREMRANGEBYSCORE key  -∞  window_start         # evict stale hits
        ZADD              key  now           now        # member = score = now (ms)
        ZCARD             key                            # count current size
        EXPIRE            key  window_seconds            # GC keys for idle IPs

The single pipeline keeps it to one network RTT per request. The current
hit is added *before* the count check; the budget compares against the
post-insert size, which is intentional (matches the in-process semantics
where ``hits.append(now)`` happens after the eviction sweep).

Fail-open: any Redis exception (unreachable, timeout, etc.) is caught and
the request is allowed through with a WARN log. Rate limiting is an
optimisation, not a correctness invariant — downing the API on a Redis
blip would be worse than honouring a temporarily un-rate-limited request.
"""
from __future__ import annotations

import time
from typing import Optional, Protocol

import structlog

logger = structlog.get_logger(__name__)


class _RedisClient(Protocol):
    """Subset of redis.Redis surface area the limiter needs."""

    def pipeline(self, transaction: bool = ...) -> "_RedisPipeline":  # pragma: no cover
        ...


class _RedisPipeline(Protocol):
    def zremrangebyscore(self, name: str, min_: float, max_: float) -> "_RedisPipeline":  # pragma: no cover
        ...

    def zadd(self, name: str, mapping: dict) -> "_RedisPipeline":  # pragma: no cover
        ...

    def zcard(self, name: str) -> "_RedisPipeline":  # pragma: no cover
        ...

    def expire(self, name: str, seconds: int) -> "_RedisPipeline":  # pragma: no cover
        ...

    def execute(self) -> list:  # pragma: no cover
        ...


KEY_PREFIX: str = "wcp:ratelimit:"


class RedisSlidingWindowLimiter:
    """One instance shared across all replicas, keyed in Redis ZSETs.

    ``budget`` requests allowed in any rolling ``window_seconds`` interval.
    """

    def __init__(
        self,
        redis_client: _RedisClient,
        *,
        budget: int,
        window_seconds: int,
    ) -> None:
        if budget < 1:
            raise ValueError("budget must be >= 1")
        if window_seconds < 1:
            raise ValueError("window_seconds must be >= 1")
        self._redis = redis_client
        self._budget = budget
        self._window_seconds = window_seconds

    @property
    def budget(self) -> int:
        return self._budget

    @property
    def window_seconds(self) -> int:
        return self._window_seconds

    def allow(self, client_ip: str) -> bool:
        """Return True if the request is within budget, False if it must be rejected.

        Redis errors degrade to fail-open (return True + log a warning).
        """
        now_ms = int(time.time() * 1000)
        window_start_ms = now_ms - self._window_seconds * 1000
        key = f"{KEY_PREFIX}{client_ip}"
        try:
            pipe = self._redis.pipeline(transaction=False)
            pipe.zremrangebyscore(key, 0, window_start_ms)
            # Score and member both equal now_ms; the member must be unique
            # per insert so we tack on a hex-suffix for the (very unlikely)
            # case of two requests landing in the same millisecond.
            pipe.zadd(key, {f"{now_ms}:{_uniq()}": now_ms})
            pipe.zcard(key)
            pipe.expire(key, self._window_seconds + 1)
            results = pipe.execute()
        except Exception as exc:
            logger.warning(
                "rate_limit_redis_unavailable_fail_open",
                client_ip=client_ip,
                error=str(exc),
            )
            return True

        # results = [removed_count, added_count, zcard_value, expire_ok]
        try:
            current_count = int(results[2])
        except (IndexError, TypeError, ValueError):
            logger.warning(
                "rate_limit_redis_unexpected_pipeline_shape",
                results_preview=str(results)[:120],
            )
            return True
        return current_count <= self._budget


# --- internals ---


_counter = 0


def _uniq() -> str:
    """Monotonic suffix so ZADD members are unique within the same ms tick.

    Reset is fine — Redis evicts by score, not member name, so collisions
    only matter inside one process; a per-process counter suffices.
    """
    global _counter
    _counter = (_counter + 1) & 0xFFFFFF
    return f"{_counter:06x}"


def build_limiter_from_settings() -> Optional["RedisSlidingWindowLimiter"]:
    """Build a Redis-backed limiter from settings, or None when REDIS_URL is empty.

    Returning None signals the middleware to fall back to the in-process
    deque-based limiter (only sensible for single-replica local dev).
    """
    from src.config.settings import settings

    if not settings.REDIS_URL:
        return None
    try:
        import redis

        client = redis.Redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=2.0,
            socket_timeout=2.0,
        )
        # Ping once so a broken DSN surfaces at startup rather than per request.
        client.ping()
        return RedisSlidingWindowLimiter(
            client,
            budget=settings.API_RATE_LIMIT_PER_MIN,
            window_seconds=settings.REDIS_RATE_LIMIT_WINDOW_SECONDS,
        )
    except Exception as exc:
        logger.warning("rate_limit_redis_build_failed_falling_back", error=str(exc))
        return None

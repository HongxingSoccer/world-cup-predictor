"""Generic Redis cache helper for hot read paths (Phase 5, design §5.1).

The class is intentionally tiny: it serialises Python primitives to JSON and
stores them with a TTL. ``get_or_set(key, ttl, factory)`` is the convenience
wrapper that powers cache-aside reads on the prediction / match / track-record
endpoints. An in-memory backend is provided so tests do not need Redis.
"""
from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

import structlog

logger = structlog.get_logger(__name__)


class CacheBackend(Protocol):
    """Subset of ``redis.Redis`` we depend on (works with both sync clients)."""

    def get(self, key: str) -> bytes | None: ...
    def setex(self, key: str, ttl_seconds: int, value: bytes) -> Any: ...
    def delete(self, *keys: str) -> int: ...


@dataclass
class InMemoryCacheBackend:
    """Test-only backend with explicit clock for TTL verification."""

    _store: dict[str, tuple[float, bytes]] = field(default_factory=dict)
    clock: Callable[[], float] = time.monotonic

    def get(self, key: str) -> bytes | None:
        item = self._store.get(key)
        if item is None:
            return None
        expires_at, value = item
        if expires_at <= self.clock():
            self._store.pop(key, None)
            return None
        return value

    def setex(self, key: str, ttl_seconds: int, value: bytes) -> None:
        self._store[key] = (self.clock() + float(ttl_seconds), value)

    def delete(self, *keys: str) -> int:
        removed = 0
        for k in keys:
            removed += int(self._store.pop(k, None) is not None)
        return removed


class RedisCache:
    """JSON-serialising cache-aside wrapper."""

    def __init__(self, backend: CacheBackend, *, namespace: str = "wcp:cache:") -> None:
        self._backend = backend
        self._ns = namespace

    def get(self, key: str) -> Any | None:
        raw = self._backend.get(self._ns + key)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("cache_unparseable", key=key)
            return None

    def set(self, key: str, value: Any, *, ttl_seconds: int) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be > 0")
        payload = json.dumps(value, default=str, ensure_ascii=False).encode()
        self._backend.setex(self._ns + key, ttl_seconds, payload)

    def delete(self, *keys: str) -> int:
        return self._backend.delete(*(self._ns + k for k in keys))

    def get_or_set(
        self, key: str, ttl_seconds: int, factory: Callable[[], Any]
    ) -> Any:
        """Return cached value, computing it via ``factory`` on miss."""
        cached = self.get(key)
        if cached is not None:
            return cached
        value = factory()
        if value is not None:
            self.set(key, value, ttl_seconds=ttl_seconds)
        return value

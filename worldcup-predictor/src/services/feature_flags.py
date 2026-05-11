"""Feature-flag service (Phase 5, design §4.4.2).

Operators toggle product features at runtime through the admin UI without a
deployment. Flag values live in Redis (so all replicas see the same state)
behind an in-process cache that refreshes every
``settings.FEATURE_FLAGS_REFRESH_SECONDS`` seconds (default 30).

Eight default flags are baked in. ``set_flag`` stores the new value in Redis
and bumps a "version" key so other replicas pick it up at their next refresh
(or immediately when called via :meth:`invalidate`).

The class is deliberately easy to fake: tests pass an in-memory dict via
:class:`InMemoryFlagBackend` instead of a live Redis client.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Protocol

import structlog

logger = structlog.get_logger(__name__)

REDIS_KEY_PREFIX: str = "wcp:feature_flags:"
REDIS_VERSION_KEY: str = "wcp:feature_flags:_version"

# Default flag set + their boot-time defaults (design §4.4.2).
DEFAULT_FLAGS: dict[str, bool] = {
    "enable_predictions": True,
    "enable_odds_analysis": True,
    "enable_ai_reports": True,
    "enable_push_notifications": True,
    "enable_payment": True,
    "enable_simulation": True,
    "enable_english": False,
    "maintenance_mode": False,
}


class FlagBackend(Protocol):
    """Minimal subset of redis-py we need; lets us inject a fake in tests."""

    def get(self, key: str) -> bytes | None: ...
    def set(self, key: str, value: bytes) -> Any: ...
    def incr(self, key: str) -> int: ...


class InMemoryFlagBackend:
    """Pure-Python stand-in for Redis used in unit tests."""

    def __init__(self) -> None:
        self._store: dict[str, bytes] = {}

    def get(self, key: str) -> bytes | None:
        return self._store.get(key)

    def set(self, key: str, value: bytes) -> None:
        self._store[key] = value

    def incr(self, key: str) -> int:
        current = int(self._store.get(key, b"0"))
        current += 1
        self._store[key] = str(current).encode()
        return current


@dataclass
class _Snapshot:
    """In-process cached view of all flag values + the version we saw."""

    values: dict[str, bool] = field(default_factory=dict)
    version: int = -1
    fetched_at: float = 0.0
    loaded: bool = False


class FeatureFlagsService:
    """Read-through cache over a Redis-like backend.

    Reads are served from the in-process snapshot if it is still fresh
    (within ``refresh_seconds``) **and** the Redis-side version counter
    has not changed. Otherwise the snapshot is rebuilt by re-fetching
    every default key from Redis. Writes go straight to Redis and bump
    the version so any other replica refreshes on its next read.
    """

    def __init__(
        self,
        backend: FlagBackend,
        *,
        defaults: dict[str, bool] | None = None,
        refresh_seconds: float = 30.0,
        clock: Any | None = None,
    ) -> None:
        self._backend = backend
        self._defaults = dict(defaults or DEFAULT_FLAGS)
        self._refresh_seconds = float(refresh_seconds)
        self._clock = clock or time.monotonic
        self._snapshot = _Snapshot()

    # --- public API -------------------------------------------------------

    def is_enabled(self, name: str) -> bool:
        """Return the current value of flag ``name`` (default if unset)."""
        if name not in self._defaults:
            raise KeyError(f"unknown feature flag: {name!r}")
        self._maybe_refresh()
        return self._snapshot.values.get(name, self._defaults[name])

    def all_flags(self) -> dict[str, bool]:
        """Snapshot of every flag's current value."""
        self._maybe_refresh()
        return {k: self._snapshot.values.get(k, v) for k, v in self._defaults.items()}

    def set_flag(self, name: str, value: bool) -> None:
        """Persist a new value to Redis and bump the version counter."""
        if name not in self._defaults:
            raise KeyError(f"unknown feature flag: {name!r}")
        if not isinstance(value, bool):
            raise TypeError("flag value must be bool")
        self._backend.set(REDIS_KEY_PREFIX + name, json.dumps(value).encode())
        self._backend.incr(REDIS_VERSION_KEY)
        self.invalidate()
        logger.info("feature_flag_set", name=name, value=value)

    def invalidate(self) -> None:
        """Force the next read to repopulate the snapshot from Redis."""
        self._snapshot = _Snapshot()

    # --- internals --------------------------------------------------------

    def _maybe_refresh(self) -> None:
        now = float(self._clock())
        snap = self._snapshot
        if snap.loaded and (now - snap.fetched_at) < self._refresh_seconds:
            current_version = self._read_version()
            if current_version == snap.version:
                return
        self._snapshot = self._reload(now)

    def _read_version(self) -> int:
        raw = self._backend.get(REDIS_VERSION_KEY)
        if raw is None:
            return 0
        try:
            return int(raw)
        except (TypeError, ValueError):
            return 0

    def _reload(self, now: float) -> _Snapshot:
        values: dict[str, bool] = {}
        for name in self._defaults:
            raw = self._backend.get(REDIS_KEY_PREFIX + name)
            if raw is None:
                continue
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                logger.warning("feature_flag_unparseable", name=name, raw=raw)
                continue
            if isinstance(parsed, bool):
                values[name] = parsed
        return _Snapshot(
            values=values,
            version=self._read_version(),
            fetched_at=now,
            loaded=True,
        )

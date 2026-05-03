"""Unit tests for src.services.cache."""
from __future__ import annotations

import pytest

from src.services.cache import InMemoryCacheBackend, RedisCache


def _cache() -> tuple[RedisCache, InMemoryCacheBackend]:
    backend = InMemoryCacheBackend()
    return RedisCache(backend), backend


def test_set_and_get_roundtrip_json():
    cache, _ = _cache()
    cache.set("k", {"a": 1, "b": [1, 2, 3]}, ttl_seconds=60)
    assert cache.get("k") == {"a": 1, "b": [1, 2, 3]}


def test_get_returns_none_on_miss():
    cache, _ = _cache()
    assert cache.get("missing") is None


def test_get_or_set_caches_factory_result():
    cache, _ = _cache()
    calls = []

    def factory():
        calls.append(1)
        return {"value": 42}

    a = cache.get_or_set("k", 60, factory)
    b = cache.get_or_set("k", 60, factory)
    assert a == b == {"value": 42}
    assert len(calls) == 1


def test_get_or_set_does_not_cache_none():
    cache, _ = _cache()
    assert cache.get_or_set("k", 60, lambda: None) is None
    assert cache.get("k") is None


def test_set_rejects_non_positive_ttl():
    cache, _ = _cache()
    with pytest.raises(ValueError):
        cache.set("k", {"x": 1}, ttl_seconds=0)


def test_ttl_expiry_with_manual_clock():
    backend = InMemoryCacheBackend()
    backend.clock = lambda: backend.clock_t  # type: ignore[attr-defined]
    backend.clock_t = 0.0  # type: ignore[attr-defined]
    cache = RedisCache(backend)
    cache.set("k", {"x": 1}, ttl_seconds=10)
    backend.clock_t = 9.0  # type: ignore[attr-defined]
    assert cache.get("k") == {"x": 1}
    backend.clock_t = 11.0  # type: ignore[attr-defined]
    assert cache.get("k") is None


def test_delete_returns_count():
    cache, _ = _cache()
    cache.set("a", 1, ttl_seconds=60)
    cache.set("b", 2, ttl_seconds=60)
    assert cache.delete("a", "b", "missing") == 2
    assert cache.get("a") is None

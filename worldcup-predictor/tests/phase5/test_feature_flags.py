"""Unit tests for src.services.feature_flags."""
from __future__ import annotations

import pytest

from src.services.feature_flags import (
    DEFAULT_FLAGS,
    FeatureFlagsService,
    InMemoryFlagBackend,
)


class _ManualClock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t


def _service(refresh: float = 30.0) -> tuple[FeatureFlagsService, InMemoryFlagBackend, _ManualClock]:
    backend = InMemoryFlagBackend()
    clock = _ManualClock()
    svc = FeatureFlagsService(backend, refresh_seconds=refresh, clock=clock)
    return svc, backend, clock


def test_returns_default_value_when_redis_empty():
    svc, _, _ = _service()
    assert svc.is_enabled("enable_predictions") is True
    assert svc.is_enabled("enable_english") is False


def test_set_flag_persists_and_reflects_in_subsequent_reads():
    svc, _, _ = _service()
    svc.set_flag("enable_english", True)
    assert svc.is_enabled("enable_english") is True


def test_unknown_flag_raises():
    svc, _, _ = _service()
    with pytest.raises(KeyError):
        svc.is_enabled("does_not_exist")
    with pytest.raises(KeyError):
        svc.set_flag("nope", True)


def test_non_bool_value_rejected():
    svc, _, _ = _service()
    with pytest.raises(TypeError):
        svc.set_flag("enable_payment", "yes")  # type: ignore[arg-type]


def test_snapshot_refresh_picks_up_external_change_via_version_bump():
    svc_a, backend, clock_a = _service(refresh=300.0)
    svc_b = FeatureFlagsService(backend, refresh_seconds=300.0, clock=clock_a)
    # Both services prime their snapshots.
    assert svc_a.is_enabled("maintenance_mode") is False
    assert svc_b.is_enabled("maintenance_mode") is False
    # Service A flips the flag.
    svc_a.set_flag("maintenance_mode", True)
    # Even though refresh window hasn't elapsed, version bump forces a reload.
    assert svc_b.is_enabled("maintenance_mode") is True


def test_snapshot_skips_redis_when_window_open_and_no_version_change():
    svc, backend, _ = _service(refresh=30.0)
    svc.is_enabled("enable_predictions")  # prime cache
    # Tamper with backend directly without bumping version → svc should NOT see change.
    backend.set("wcp:feature_flags:enable_predictions", b"false")
    assert svc.is_enabled("enable_predictions") is True


def test_all_flags_returns_full_default_set():
    svc, _, _ = _service()
    flags = svc.all_flags()
    assert set(flags) == set(DEFAULT_FLAGS)

"""Smoke tests for GET /api/v1/fx/usd-cny.

Network failures must always degrade to a non-zero rate so the subscribe
page never blanks the CNY column. The frankfurter.app upstream is mocked
out via monkeypatching the module-level fetcher.
"""
from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from src.api import routes
from src.api.main import app


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app, headers={})


@pytest.fixture(autouse=True)
def _reset_cache():
    """Drop the in-process FX cache between tests."""
    routes.fx._cache.update({"rate": None, "source": None, "as_of": None, "fetched_at": 0.0})
    yield


def test_fx_returns_fallback_when_upstream_unreachable(monkeypatch, client):
    monkeypatch.setattr(routes.fx, "_fetch_upstream", lambda: None)
    response = client.get("/api/v1/fx/usd-cny")
    assert response.status_code == 200
    body = response.json()
    assert body["pair"] == "USD/CNY"
    assert body["rate"] == routes.fx.FALLBACK_RATE
    assert body["source"] == routes.fx.FALLBACK_SOURCE


def test_fx_returns_live_rate_and_caches(monkeypatch, client):
    fixed_dt = datetime(2026, 5, 7, tzinfo=UTC)
    calls = {"n": 0}

    def fake_fetch():
        calls["n"] += 1
        return 7.13, fixed_dt

    monkeypatch.setattr(routes.fx, "_fetch_upstream", fake_fetch)

    first = client.get("/api/v1/fx/usd-cny").json()
    assert first["rate"] == pytest.approx(7.13, abs=1e-3)
    assert first["source"] == "frankfurter.app"
    assert first["cached"] is False

    # Second call within TTL must hit the cache, not re-fetch.
    second = client.get("/api/v1/fx/usd-cny").json()
    assert second["cached"] is True
    assert calls["n"] == 1

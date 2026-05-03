"""Integration tests for the Phase 5 admin API."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api.dependencies import get_db_session, get_feature_flags
from src.api.main import app
from src.config.settings import settings
from src.services.feature_flags import FeatureFlagsService, InMemoryFlagBackend

ADMIN_TOKEN = "test-admin-token-please-change-in-production"


@pytest.fixture()
def client(db_session, monkeypatch):  # type: ignore[no-untyped-def]
    monkeypatch.setattr(settings, "ADMIN_API_TOKEN", ADMIN_TOKEN)
    monkeypatch.setattr(settings, "API_KEY", "")  # disable API key middleware
    flags = FeatureFlagsService(InMemoryFlagBackend(), refresh_seconds=60)

    def _db():
        yield db_session

    app.dependency_overrides[get_db_session] = _db
    app.dependency_overrides[get_feature_flags] = lambda: flags
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _h() -> dict[str, str]:
    return {"X-Admin-Token": ADMIN_TOKEN}


def test_admin_overview_returns_card_set(client):
    r = client.get("/api/v1/admin", headers=_h())
    assert r.status_code == 200
    body = r.json()
    labels = {c["label"] for c in body["cards"]}
    assert {"users_total", "predictions_total", "reports_total", "push_24h"} <= labels


def test_admin_users_pagination_returns_total(client):
    r = client.get("/api/v1/admin/users?limit=10&offset=0", headers=_h())
    assert r.status_code == 200
    body = r.json()
    assert "total" in body and "items" in body
    assert isinstance(body["items"], list)


def test_get_flags_returns_default_set(client):
    r = client.get("/api/v1/admin/system/flags", headers=_h())
    assert r.status_code == 200
    flags = r.json()["flags"]
    assert flags["enable_predictions"] is True
    assert flags["maintenance_mode"] is False


def test_put_flag_updates_value(client):
    r = client.put(
        "/api/v1/admin/system/flags",
        headers=_h(),
        json={"name": "maintenance_mode", "value": True},
    )
    assert r.status_code == 200
    assert r.json()["flags"]["maintenance_mode"] is True


def test_put_unknown_flag_returns_404(client):
    r = client.put(
        "/api/v1/admin/system/flags",
        headers=_h(),
        json={"name": "not_a_flag", "value": True},
    )
    assert r.status_code == 404


def test_admin_routes_reject_missing_token(client):
    r = client.get("/api/v1/admin")
    assert r.status_code == 401


def test_admin_routes_reject_wrong_token(client):
    r = client.get("/api/v1/admin", headers={"X-Admin-Token": "wrong"})
    assert r.status_code == 401


def test_admin_disabled_when_token_unset(monkeypatch, db_session):
    monkeypatch.setattr(settings, "ADMIN_API_TOKEN", "")
    monkeypatch.setattr(settings, "API_KEY", "")

    def _db():
        yield db_session

    app.dependency_overrides[get_db_session] = _db
    try:
        with TestClient(app) as c:
            r = c.get("/api/v1/admin", headers={"X-Admin-Token": "anything"})
            assert r.status_code == 404
    finally:
        app.dependency_overrides.clear()

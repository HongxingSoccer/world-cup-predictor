"""Smoke tests for POST /api/v1/client-errors — browser error sentinel.

The endpoint is fire-and-forget: it must always return 200 + {"status": "logged"}
regardless of payload validity, so a flaky browser-side reporter never causes
cascading failures.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api.main import app


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app, headers={})


def test_client_error_logs_full_payload(client):
    response = client.post(
        "/api/v1/client-errors",
        json={
            "digest": "abc123",
            "pathname": "/match/1",
            "message": "Cannot read properties of undefined",
        },
    )
    assert response.status_code == 200
    assert response.json() == {"status": "logged"}


def test_client_error_accepts_partial_payload(client):
    """Missing fields must not 400 — we never want to reject a sentinel ping."""
    response = client.post("/api/v1/client-errors", json={})
    assert response.status_code == 200
    assert response.json() == {"status": "logged"}


def test_client_error_ignores_extra_fields(client):
    """Extra fields are silently dropped (extra='ignore' in the model)."""
    response = client.post(
        "/api/v1/client-errors",
        json={
            "digest": "x",
            "stack": "irrelevant",
            "user_id": 99,
        },
    )
    assert response.status_code == 200

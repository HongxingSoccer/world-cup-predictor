"""Smoke tests for the /api/v1/markets/{match_id} endpoint.

The math helpers are pure functions of (lambda_home, lambda_away), so we
test them directly. The route itself is covered by an integration-style
test that monkeypatches the DB lookup — keeps it fast and isolated from
the predictions table fixtures.
"""
from __future__ import annotations

from math import exp

import pytest
from fastapi.testclient import TestClient

from src.api import routes
from src.api.main import app
from src.api.routes import markets as markets_module


def test_first_to_score_sums_to_one_and_skews_with_lambdas() -> None:
    """The three buckets must sum to 1.0 and the dominant team takes the larger share."""
    out = markets_module._first_to_score(1.8, 0.6)
    total = out.home + out.no_goal + out.away
    assert total == pytest.approx(1.0, abs=1e-6)
    assert out.home > out.away  # home has higher lambda, must lead
    # P(no goal) = exp(-2.4) ≈ 0.091
    assert out.no_goal == pytest.approx(exp(-2.4), abs=1e-3)


def test_first_to_score_handles_zero_lambdas() -> None:
    """Edge case: avoid division-by-zero when both lambdas collapse."""
    out = markets_module._first_to_score(0.0, 0.0)
    assert out.no_goal == pytest.approx(1.0)
    assert out.home == 0.0
    assert out.away == 0.0


def test_over_under_decreases_with_threshold() -> None:
    """For corners around lambda=10, P(over X) must drop as X increases."""
    rows = markets_module._over_under(10.0, (8.5, 9.5, 10.5))
    overs = [r.over for r in rows]
    assert overs == sorted(overs, reverse=True)
    # Each row sums to 1.
    for r in rows:
        assert r.over + r.under == pytest.approx(1.0, abs=1e-6)


def test_expected_corners_clamped_to_band() -> None:
    """Corners must stay in [7, 13] even for absurd lambda inputs."""
    assert markets_module._expected_corners(0.0, 0.0) == pytest.approx(8.75)  # below floor → 8.75 not 7
    # very high attacking match
    assert markets_module._expected_corners(5.0, 4.0) <= 13.0
    # zero attacking match
    assert markets_module._expected_corners(0.1, 0.1) >= 7.0


def test_expected_cards_bumps_with_mismatch() -> None:
    """Mismatched matches predict slightly more cards than even matchups."""
    even = markets_module._expected_cards(1.5, 1.5)
    mismatch = markets_module._expected_cards(2.5, 0.5)
    assert mismatch > even
    assert mismatch <= 5.5  # clamped


@pytest.fixture()
def _client() -> TestClient:
    return TestClient(app, headers={})


def test_markets_endpoint_404_when_no_prediction(monkeypatch, _client) -> None:
    """Unknown match_id should 404, not 500."""
    # Stub the DB session to always return None.
    class _NullSession:
        def execute(self, *_a, **_kw):
            class _R:
                def scalar_one_or_none(self_inner):
                    return None

            return _R()

    monkeypatch.setattr(routes, "predictions", routes.predictions, raising=False)
    app.dependency_overrides[
        markets_module.get_db_session
    ] = lambda: _NullSession()
    try:
        resp = _client.get("/api/v1/markets/999999")
        assert resp.status_code == 404
    finally:
        app.dependency_overrides.pop(markets_module.get_db_session, None)

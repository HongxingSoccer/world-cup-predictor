"""Smoke tests for GET /api/v1/matches/{id} — pure-read match-detail route.

The route never runs the model: missing predictions / odds / form / H2H must
each gracefully degrade to None / 0 instead of erroring. These tests cover
both the empty-DB path (no prediction, no H2H, no priors) and the populated
path (prediction + H2H row + 5 prior finished matches per side).
"""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from src.api.dependencies import get_db_session
from src.api.main import app
from src.config.settings import settings
from src.models.h2h_record import H2HRecord
from src.models.prediction import Prediction


@pytest.fixture()
def api_client(db_session):  # type: ignore[no-untyped-def]
    app.dependency_overrides[get_db_session] = lambda: db_session
    yield TestClient(app, headers={})
    app.dependency_overrides.clear()


def test_match_detail_404_for_unknown_match(api_client):
    response = api_client.get("/api/v1/matches/99999")
    assert response.status_code == 404


def test_match_detail_returns_metadata_with_no_prediction(
    api_client, db_session, make_match, utc
):
    match = make_match(utc(2026, 6, 12, 18), status="scheduled")
    db_session.flush()

    response = api_client.get(f"/api/v1/matches/{match.id}")
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["match_id"] == match.id
    assert body["home_team"] == "Alpha"
    assert body["away_team"] == "Beta"
    assert body["status"] == "scheduled"
    # No prediction yet → all model fields are null but the page still renders.
    assert body["prob_home_win"] is None
    assert body["confidence_score"] is None
    assert body["score_matrix"] is None
    # No prior finished matches → empty form rows, not an error.
    assert body["team_stats"] == []
    # No H2H row → zero summary, not null.
    assert body["h2h"]["total_matches"] == 0
    assert body["h2h"]["avg_goals"] == 0.0


def test_match_detail_includes_latest_active_prediction(
    api_client, db_session, make_match, utc
):
    match = make_match(utc(2026, 6, 12, 18), status="scheduled")
    db_session.flush()

    db_session.add(
        Prediction(
            match_id=match.id,
            model_version=settings.ACTIVE_MODEL_NAME,
            feature_version="v1",
            prob_home_win=Decimal("0.5500"),
            prob_draw=Decimal("0.2500"),
            prob_away_win=Decimal("0.2000"),
            lambda_home=Decimal("1.500"),
            lambda_away=Decimal("0.900"),
            score_matrix=[[0.1, 0.05], [0.2, 0.1]],
            top_scores=[{"score": "1-0", "prob": 0.2}],
            over_under_probs={"2.5": {"over": 0.45, "under": 0.55}},
            btts_prob=Decimal("0.5000"),
            confidence_score=72,
            confidence_level="medium",
            features_snapshot={"feature_count": 28},
            content_hash="a" * 64,
            published_at=match.match_date - timedelta(hours=1),
        )
    )
    db_session.flush()

    response = api_client.get(f"/api/v1/matches/{match.id}")
    assert response.status_code == 200
    body = response.json()
    assert body["prob_home_win"] == pytest.approx(0.55, abs=1e-3)
    assert body["confidence_level"] == "medium"
    assert body["confidence_score"] == 72
    # No odds_analysis rows seeded → empty list (not null) when prediction exists.
    assert body["odds_analysis"] == []
    assert body["top_signal_level"] == 0


def test_match_detail_aggregates_recent_form(api_client, db_session, make_match, utc):
    """Past 5 finished matches per side should populate the team_stats rows."""
    target = make_match(utc(2026, 6, 20, 18), status="scheduled")
    # Home team (Alpha) plays 3 priors: W (3-0), L (0-2), W (2-1)
    make_match(utc(2026, 6, 1), home_score=3, away_score=0)
    make_match(utc(2026, 6, 5), home_score=0, away_score=2)
    make_match(utc(2026, 6, 10), home_score=2, away_score=1)
    db_session.flush()

    response = api_client.get(f"/api/v1/matches/{target.id}")
    assert response.status_code == 200
    body = response.json()
    rows = body["team_stats"]
    assert len(rows) == 3
    # Alpha's 3 home games: 2 wins / 3 = 67% (rounded)
    assert rows[0]["home"] == "67%"


def test_match_detail_h2h_oriented_to_home_perspective(
    api_client, db_session, make_match, seed_world, utc
):
    """H2H summary must flip team_a/team_b to home/away as the API caller expects."""
    target = make_match(utc(2026, 6, 20, 18), status="scheduled")
    home_id = seed_world["home_team_id"]
    away_id = seed_world["away_team_id"]
    a_id, b_id = sorted([home_id, away_id])

    # Canonical (a < b) row. Whichever side ends up as `team_a`, give that
    # side 5 wins, the other 1 — let the API renormalise.
    db_session.add(
        H2HRecord(
            team_a_id=a_id,
            team_b_id=b_id,
            total_matches=8,
            team_a_wins=5,
            team_b_wins=1,
            draws=2,
            team_a_goals=14,
            team_b_goals=6,
        )
    )
    db_session.flush()

    response = api_client.get(f"/api/v1/matches/{target.id}")
    assert response.status_code == 200
    h2h = response.json()["h2h"]
    assert h2h["total_matches"] == 8
    assert h2h["draws"] == 2
    assert h2h["home_wins"] + h2h["away_wins"] == 6
    # avg_goals = (14 + 6) / 8 = 2.5
    assert h2h["avg_goals"] == pytest.approx(2.5, abs=1e-3)

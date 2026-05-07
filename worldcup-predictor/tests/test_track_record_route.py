"""Smoke tests for /api/v1/track-record/* — the public scoreboard endpoints.

Empty-DB path is the most-important contract: pre-tournament, no predictions
have been settled yet, so `track_record_stats` is empty. The frontend
renders a "data lands when the tournament starts" empty state — that's only
possible if the API returns 200 + zero defaults instead of 404.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from src.api.dependencies import get_db_session
from src.api.main import app
from src.models.prediction_result import PredictionResult
from src.models.track_record_stat import TrackRecordStat


@pytest.fixture()
def api_client(db_session):  # type: ignore[no-untyped-def]
    app.dependency_overrides[get_db_session] = lambda: db_session
    yield TestClient(app, headers={})
    app.dependency_overrides.clear()


def test_overview_returns_zero_default_when_table_empty(api_client):
    """Pre-tournament (no settled rows) must still return 200 with zero metrics."""
    response = api_client.get(
        "/api/v1/track-record/overview",
        params={"statType": "overall", "period": "all_time"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["stat_type"] == "overall"
    assert body["period"] == "all_time"
    assert body["total_predictions"] == 0
    assert body["hits"] == 0
    assert body["hit_rate"] == 0.0
    assert body["roi"] == 0.0
    assert body["updated_at"] is None


def test_overview_returns_persisted_row_when_present(api_client, db_session):
    db_session.add(
        TrackRecordStat(
            stat_type="overall",
            period="all_time",
            total_predictions=20,
            hits=11,
            hit_rate=Decimal("0.5500"),
            total_pnl_units=Decimal("3.4000"),
            roi=Decimal("0.1700"),
            current_streak=3,
            best_streak=4,
        )
    )
    db_session.flush()

    response = api_client.get(
        "/api/v1/track-record/overview",
        params={"statType": "overall", "period": "all_time"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total_predictions"] == 20
    assert body["hit_rate"] == pytest.approx(0.55, abs=1e-3)
    assert body["roi"] == pytest.approx(0.17, abs=1e-3)
    assert body["best_streak"] == 4


def test_roi_chart_returns_one_default_row_per_stat_type_when_empty(api_client):
    """All six known stat-types should be present even when DB is empty."""
    response = api_client.get(
        "/api/v1/track-record/roi-chart", params={"period": "all_time"}
    )
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert len(body) == 6
    types = {row["stat_type"] for row in body}
    assert types == {"overall", "1x2", "score", "ou25", "btts", "positive_ev"}
    for row in body:
        assert row["total_predictions"] == 0


def test_timeseries_empty_when_no_settled_results(api_client):
    response = api_client.get(
        "/api/v1/track-record/timeseries", params={"period": "all_time"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["period"] == "all_time"
    assert body["points"] == []


def test_timeseries_accumulates_pnl_per_day(api_client, db_session, make_match, utc):
    """Two settled rows on different days → two cumulative-ROI points."""
    m1 = make_match(utc(2026, 6, 12), home_score=2, away_score=1)
    m2 = make_match(utc(2026, 6, 13), home_score=1, away_score=1)
    db_session.flush()

    base = datetime.now(timezone.utc) - timedelta(days=2)
    db_session.add_all([
        PredictionResult(
            prediction_id=1,
            match_id=m1.id,
            actual_home_score=2,
            actual_away_score=1,
            result_1x2_hit=True,
            result_score_hit=False,
            best_ev_outcome="home",
            best_ev_odds=Decimal("1.900"),
            best_ev_hit=True,
            pnl_unit=Decimal("0.9000"),
            settled_at=base,
        ),
        PredictionResult(
            prediction_id=2,
            match_id=m2.id,
            actual_home_score=1,
            actual_away_score=1,
            result_1x2_hit=True,
            result_score_hit=True,
            pnl_unit=Decimal("0.5000"),
            settled_at=base + timedelta(days=1),
        ),
    ])
    db_session.flush()

    response = api_client.get(
        "/api/v1/track-record/timeseries", params={"period": "all_time"}
    )
    assert response.status_code == 200
    body = response.json()
    points = body["points"]
    assert len(points) == 2
    assert points[0]["cumulative_pnl"] == pytest.approx(0.9, abs=1e-3)
    assert points[1]["cumulative_pnl"] == pytest.approx(1.4, abs=1e-3)
    assert points[1]["settled_count"] == 2


def test_overview_clamps_unknown_stat_type(api_client):
    """Bogus statType should fall back to 'overall' instead of erroring."""
    response = api_client.get(
        "/api/v1/track-record/overview",
        params={"statType": "nonsense", "period": "all_time"},
    )
    assert response.status_code == 200
    assert response.json()["stat_type"] == "overall"

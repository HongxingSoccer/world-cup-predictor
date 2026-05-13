"""Integration tests for the M9 FastAPI endpoints.

Covers the three routes in :mod:`src.api.routes.hedge`:

    POST /api/v1/hedge/calculate
    POST /api/v1/hedge/parlay
    GET  /api/v1/hedge/live-odds/{match_id}

Notes:
    * The test sqlite engine has ``foreign_keys`` enabled by the
      project-wide conftest, so FK behaviour mirrors production.
    * ``settings.API_KEY`` defaults to empty in test config → the
      middleware bypasses auth. One test sets a key to verify the 401
      path explicitly.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.api.dependencies import get_db_session, get_prediction_service
from src.api.main import app as _app
from src.config.settings import settings
from src.models.hedge_scenario import HedgeCalculation, HedgeScenario, ParlayLeg
from src.models.odds_snapshot import OddsSnapshot

HEDGE_DISCLAIMER_FRAGMENT = "本平台仅提供数据分析参考"


# -----------------------------------------------------------------------------
# Local helpers
# -----------------------------------------------------------------------------


def _make_snapshot(
    db_session: Session,
    *,
    match_id: int,
    bookmaker: str,
    market_type: str = "1x2",
    home: Decimal | None = None,
    draw: Decimal | None = None,
    away: Decimal | None = None,
    over: Decimal | None = None,
    under: Decimal | None = None,
    minutes_ago: int = 1,
) -> OddsSnapshot:
    snap = OddsSnapshot(
        match_id=match_id,
        bookmaker=bookmaker,
        market_type=market_type,
        outcome_home=home,
        outcome_draw=draw,
        outcome_away=away,
        outcome_over=over,
        outcome_under=under,
        snapshot_at=datetime.now(UTC) - timedelta(minutes=minutes_ago),
        data_source="test",
    )
    db_session.add(snap)
    db_session.flush()
    return snap


@pytest.fixture()
def client(db_session: Session) -> Iterator[TestClient]:
    """TestClient bound to the shared in-memory db_session.

    Overrides:
        get_db_session    → use the test session
        get_prediction_service → None (advisor degrades to math-only)
    """
    _app.dependency_overrides[get_db_session] = lambda: db_session
    _app.dependency_overrides[get_prediction_service] = lambda: None
    yield TestClient(_app)
    _app.dependency_overrides.clear()


# -----------------------------------------------------------------------------
# POST /calculate
# -----------------------------------------------------------------------------


class TestHedgeCalculateEndpoint:
    def test_returns_disclaimer(
        self, client: TestClient, db_session: Session, make_match, utc
    ) -> None:
        match = make_match(utc(2026, 6, 1, 18), status="scheduled")
        _make_snapshot(
            db_session,
            match_id=match.id,
            bookmaker="pinnacle",
            home=Decimal("2.10"),
            draw=Decimal("3.40"),
            away=Decimal("4.20"),
        )
        body = {
            "match_id": match.id,
            "original_stake": "100",
            "original_odds": "2.10",
            "original_outcome": "home",
            "original_market": "1x2",
            "hedge_mode": "full",
        }
        r = client.post("/api/v1/hedge/calculate", json=body)
        assert r.status_code == 200, r.text
        payload = r.json()
        assert HEDGE_DISCLAIMER_FRAGMENT in payload["disclaimer"]

    def test_writes_scenario_and_calculations(
        self, client: TestClient, db_session: Session, make_match, utc
    ) -> None:
        match = make_match(utc(2026, 6, 1, 18), status="scheduled")
        # Two bookmakers covering draw + away; pick the best per outcome.
        _make_snapshot(
            db_session,
            match_id=match.id,
            bookmaker="pinnacle",
            draw=Decimal("3.40"),
            away=Decimal("4.20"),
        )
        _make_snapshot(
            db_session,
            match_id=match.id,
            bookmaker="bet365",
            draw=Decimal("3.50"),  # better draw odds → wins
            away=Decimal("4.10"),
        )

        body = {
            "match_id": match.id,
            "original_stake": "100",
            "original_odds": "2.10",
            "original_outcome": "home",
            "original_market": "1x2",
            "hedge_mode": "full",
        }
        r = client.post("/api/v1/hedge/calculate", json=body)
        assert r.status_code == 200, r.text
        payload = r.json()

        # 2 recommendations: one per non-home outcome (draw + away).
        assert len(payload["recommendations"]) == 2
        outcomes = {rec["hedge_outcome"] for rec in payload["recommendations"]}
        assert outcomes == {"draw", "away"}

        # Best draw bookmaker should be bet365 (3.50 > 3.40).
        draw_rec = next(
            r for r in payload["recommendations"] if r["hedge_outcome"] == "draw"
        )
        assert draw_rec["hedge_bookmaker"] == "bet365"
        assert Decimal(draw_rec["hedge_odds"]) == Decimal("3.500")

        # Scenario + calculations persisted.
        scenario = (
            db_session.query(HedgeScenario)
            .filter(HedgeScenario.id == payload["scenario_id"])
            .one()
        )
        assert scenario.scenario_type == "single"
        assert scenario.match_id == match.id

        calcs = (
            db_session.query(HedgeCalculation)
            .filter(HedgeCalculation.scenario_id == scenario.id)
            .all()
        )
        assert len(calcs) == 2

    def test_no_recent_odds_returns_empty_recommendations_with_warning(
        self, client: TestClient, db_session: Session, make_match, utc
    ) -> None:
        match = make_match(utc(2026, 6, 1, 18), status="scheduled")
        # Older snapshot — outside the 10-minute window.
        _make_snapshot(
            db_session,
            match_id=match.id,
            bookmaker="pinnacle",
            draw=Decimal("3.40"),
            away=Decimal("4.20"),
            minutes_ago=30,
        )
        body = {
            "match_id": match.id,
            "original_stake": "100",
            "original_odds": "2.10",
            "original_outcome": "home",
            "original_market": "1x2",
            "hedge_mode": "full",
        }
        r = client.post("/api/v1/hedge/calculate", json=body)
        assert r.status_code == 200, r.text
        payload = r.json()
        assert payload["recommendations"] == []
        assert "no recent odds" in payload["warning"]

    def test_missing_api_key_returns_401(
        self,
        client: TestClient,
        db_session: Session,
        make_match,
        utc,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Set a key on the running app's settings (middleware reads at request time).
        monkeypatch.setattr(settings, "API_KEY", "test-key")
        match = make_match(utc(2026, 6, 1, 18), status="scheduled")
        body = {
            "match_id": match.id,
            "original_stake": "100",
            "original_odds": "2.10",
            "original_outcome": "home",
            "original_market": "1x2",
            "hedge_mode": "full",
        }
        r = client.post("/api/v1/hedge/calculate", json=body)
        assert r.status_code == 401, r.text


# -----------------------------------------------------------------------------
# POST /parlay
# -----------------------------------------------------------------------------


class TestHedgeParlayEndpoint:
    def test_writes_scenario_with_legs(
        self, client: TestClient, db_session: Session, make_match, utc
    ) -> None:
        # Three matches for a three-leg parlay. Bookmaker covering the
        # opposite of the third leg's outcome.
        m1 = make_match(utc(2026, 6, 1, 18), status="finished")
        m2 = make_match(utc(2026, 6, 2, 18), status="finished")
        m3 = make_match(utc(2026, 6, 3, 18), status="scheduled")
        _make_snapshot(
            db_session,
            match_id=m3.id,
            bookmaker="pinnacle",
            # leg3.outcome = "home" → hedge with best of draw / away.
            draw=Decimal("3.40"),
            away=Decimal("4.10"),
        )

        body = {
            "original_stake": "50",
            "legs": [
                {
                    "match_id": m1.id,
                    "outcome": "home",
                    "odds": "1.85",
                    "is_settled": True,
                    "is_won": True,
                },
                {
                    "match_id": m2.id,
                    "outcome": "over",
                    "odds": "1.90",
                    "is_settled": True,
                    "is_won": True,
                },
                {
                    "match_id": m3.id,
                    "outcome": "home",
                    "odds": "2.20",
                    "is_settled": False,
                },
            ],
            "hedge_mode": "full",
        }
        r = client.post("/api/v1/hedge/parlay", json=body)
        assert r.status_code == 200, r.text
        payload = r.json()
        assert HEDGE_DISCLAIMER_FRAGMENT in payload["disclaimer"]
        assert payload["last_leg_match_id"] == m3.id

        # parlay_potential = 50 × 1.85 × 1.90 × 2.20 = 386.65
        assert Decimal(payload["parlay_potential"]) == Decimal("386.65")

        scenario_id = payload["scenario_id"]
        legs = (
            db_session.query(ParlayLeg)
            .filter(ParlayLeg.scenario_id == scenario_id)
            .order_by(ParlayLeg.leg_order)
            .all()
        )
        assert len(legs) == 3
        assert [int(le.leg_order) for le in legs] == [1, 2, 3]


# -----------------------------------------------------------------------------
# GET /live-odds/{match_id}
# -----------------------------------------------------------------------------


class TestHedgeLiveOddsEndpoint:
    def test_returns_grouped_by_market(
        self, client: TestClient, db_session: Session, make_match, utc
    ) -> None:
        match = make_match(utc(2026, 6, 1, 18), status="scheduled")
        _make_snapshot(
            db_session,
            match_id=match.id,
            bookmaker="pinnacle",
            market_type="1x2",
            home=Decimal("2.10"),
            draw=Decimal("3.40"),
            away=Decimal("4.20"),
        )
        _make_snapshot(
            db_session,
            match_id=match.id,
            bookmaker="bet365",
            market_type="1x2",
            home=Decimal("2.15"),
            draw=Decimal("3.30"),
            away=Decimal("4.30"),
        )
        _make_snapshot(
            db_session,
            match_id=match.id,
            bookmaker="pinnacle",
            market_type="over_under",
            over=Decimal("1.85"),
            under=Decimal("1.95"),
        )

        r = client.get(f"/api/v1/hedge/live-odds/{match.id}")
        assert r.status_code == 200, r.text
        payload = r.json()
        assert payload["match_id"] == match.id
        markets = {m["market"]: m for m in payload["markets"]}
        assert "1x2" in markets and "over_under" in markets

        home_entry = next(
            e for e in markets["1x2"]["entries"] if e["outcome"] == "home"
        )
        # 2.15 > 2.10 → bet365 wins on home
        assert home_entry["best_bookmaker"] == "bet365"
        assert Decimal(home_entry["best_odds"]) == Decimal("2.150")

    def test_no_snapshots_in_12_hours_returns_404(
        self, client: TestClient, db_session: Session, make_match, utc
    ) -> None:
        match = make_match(utc(2026, 6, 1, 18), status="scheduled")
        # Older than 12 hours.
        snap = OddsSnapshot(
            match_id=match.id,
            bookmaker="pinnacle",
            market_type="1x2",
            outcome_home=Decimal("2.10"),
            outcome_draw=Decimal("3.40"),
            outcome_away=Decimal("4.20"),
            snapshot_at=datetime.now(UTC) - timedelta(hours=24),
            data_source="test",
        )
        db_session.add(snap)
        db_session.flush()

        r = client.get(f"/api/v1/hedge/live-odds/{match.id}")
        assert r.status_code == 404

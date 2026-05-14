"""Integration tests for :class:`ArbScanner` — feeds it real odds rows
against an in-memory SQLite session."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from src.ml.arbitrage.scanner import ArbScanner
from src.models.arbitrage import ArbOpportunity
from src.models.odds_snapshot import OddsSnapshot


def _snap(
    session: Session,
    match_id: int,
    bookmaker: str,
    *,
    market_type: str = "1x2",
    home: str | None = None,
    draw: str | None = None,
    away: str | None = None,
    over: str | None = None,
    under: str | None = None,
    minutes_ago: int = 1,
) -> OddsSnapshot:
    snap = OddsSnapshot(
        match_id=match_id,
        bookmaker=bookmaker,
        market_type=market_type,
        outcome_home=Decimal(home) if home else None,
        outcome_draw=Decimal(draw) if draw else None,
        outcome_away=Decimal(away) if away else None,
        outcome_over=Decimal(over) if over else None,
        outcome_under=Decimal(under) if under else None,
        snapshot_at=datetime.now(UTC) - timedelta(minutes=minutes_ago),
        data_source="test",
    )
    session.add(snap)
    session.flush()
    return snap


class TestScan:
    def test_detects_classic_1x2_arb_across_books(
        self, db_session: Session, make_match, utc
    ) -> None:
        match = make_match(utc(2026, 6, 5, 18), status="scheduled")
        # Three bookmakers, each best on one outcome — pushes the
        # implied sum below 1.0.
        _snap(db_session, match.id, "book_a", home="2.50", draw="3.10", away="3.30")
        _snap(db_session, match.id, "book_b", home="2.40", draw="3.60", away="3.40")
        _snap(db_session, match.id, "book_c", home="2.35", draw="3.30", away="3.80")

        summary = ArbScanner.scan(db_session)
        assert summary["opportunities_persisted"] == 1

        opp = db_session.query(ArbOpportunity).one()
        assert opp.status == "active"
        assert opp.market_type == "1x2"
        assert opp.profit_margin > Decimal("0.02")
        assert "home" in opp.best_odds and "draw" in opp.best_odds and "away" in opp.best_odds

    def test_skips_finished_matches(
        self, db_session: Session, make_match, utc
    ) -> None:
        match = make_match(utc(2026, 6, 5, 18), status="finished")
        _snap(db_session, match.id, "book_a", home="2.50", draw="3.60", away="3.80")

        summary = ArbScanner.scan(db_session)
        assert summary["opportunities_persisted"] == 0

    def test_expires_previous_opportunity_when_arb_disappears(
        self, db_session: Session, make_match, utc
    ) -> None:
        match = make_match(utc(2026, 6, 5, 18), status="scheduled")
        # First sweep: classic arb persisted (recent snapshots).
        _snap(db_session, match.id, "book_a", home="2.50", minutes_ago=1)
        _snap(db_session, match.id, "book_b", draw="3.60", minutes_ago=1)
        _snap(db_session, match.id, "book_c", away="3.80", minutes_ago=1)
        ArbScanner.scan(db_session)
        active = db_session.query(ArbOpportunity).filter_by(status="active").count()
        assert active == 1

        # Time passes — original arb snapshots fall outside the 10-min
        # window. Fresh snapshots arrive with bookmaker-margin pricing,
        # so the new best-of doesn't form an arb.
        db_session.query(OddsSnapshot).update(
            {OddsSnapshot.snapshot_at: datetime.now(UTC) - timedelta(minutes=30)},
        )
        db_session.flush()
        _snap(
            db_session,
            match.id,
            "tight_book",
            home="2.10",
            draw="3.10",
            away="3.20",
            minutes_ago=0,
        )
        ArbScanner.scan(db_session)

        active = db_session.query(ArbOpportunity).filter_by(status="active").count()
        expired = db_session.query(ArbOpportunity).filter_by(status="expired").count()
        assert active == 0
        assert expired == 1

    def test_ignores_stale_snapshots(
        self, db_session: Session, make_match, utc
    ) -> None:
        match = make_match(utc(2026, 6, 5, 18), status="scheduled")
        # All snapshots outside the 10-minute window.
        _snap(db_session, match.id, "book_a", home="2.50", minutes_ago=30)
        _snap(db_session, match.id, "book_b", draw="3.60", minutes_ago=30)
        _snap(db_session, match.id, "book_c", away="3.80", minutes_ago=30)

        summary = ArbScanner.scan(db_session)
        assert summary["matches_examined"] == 0

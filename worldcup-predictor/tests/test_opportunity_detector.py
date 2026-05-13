"""Tests for :class:`HedgeOpportunityDetector` (M9.5 live monitor heart)."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from src.ml.hedge.opportunity_detector import HedgeOpportunityDetector
from src.models.odds_snapshot import OddsSnapshot
from src.models.user import User
from src.models.user_position import UserPosition


def _make_user(db_session: Session) -> User:
    user = User(uuid=uuid.uuid4(), nickname="trader", subscription_tier="basic")
    db_session.add(user)
    db_session.flush()
    return user


def _add_snapshot(
    session: Session,
    *,
    match_id: int,
    bookmaker: str = "pinnacle",
    market_type: str = "1x2",
    home: Decimal | None = None,
    draw: Decimal | None = None,
    away: Decimal | None = None,
    over: Decimal | None = None,
    under: Decimal | None = None,
    when: datetime,
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
        snapshot_at=when,
        data_source="test",
    )
    session.add(snap)
    session.flush()
    return snap


def _make_position(
    db_session: Session,
    user: User,
    match_id: int,
    *,
    market: str,
    outcome: str,
    odds: str,
    placed_at: datetime,
) -> UserPosition:
    pos = UserPosition(
        user_id=user.id,
        match_id=match_id,
        platform="pinnacle",
        market=market,
        outcome=outcome,
        stake=Decimal("100"),
        odds=Decimal(odds),
        placed_at=placed_at,
    )
    db_session.add(pos)
    db_session.flush()
    return pos


class TestNoOpportunity:
    def test_no_snapshots_returns_empty(
        self, db_session: Session, make_match, utc
    ) -> None:
        user = _make_user(db_session)
        match = make_match(utc(2026, 6, 5, 18), status="scheduled")
        pos = _make_position(
            db_session,
            user,
            match.id,
            market="1x2",
            outcome="home",
            odds="2.10",
            placed_at=datetime.now(UTC) - timedelta(hours=2),
        )
        result = HedgeOpportunityDetector.detect(db_session, pos)
        assert result["has_opportunity"] is False
        assert result["trigger_reason"] is None

    def test_btts_market_unsupported_returns_empty(
        self, db_session: Session, make_match, utc
    ) -> None:
        """BTTS isn't in _REVERSE_OUTCOMES — should bail out cleanly."""
        user = _make_user(db_session)
        match = make_match(utc(2026, 6, 5, 18), status="scheduled")
        pos = _make_position(
            db_session,
            user,
            match.id,
            market="btts",
            outcome="yes",
            odds="1.90",
            placed_at=datetime.now(UTC) - timedelta(hours=2),
        )
        result = HedgeOpportunityDetector.detect(db_session, pos)
        assert result["has_opportunity"] is False


class TestOddsShiftTrigger:
    def test_15pct_shift_in_users_favour_fires(
        self, db_session: Session, make_match, utc
    ) -> None:
        """Baseline draw=3.0 (at bet time), now=3.50 → +16.6% shift → trigger."""
        user = _make_user(db_session)
        match = make_match(utc(2026, 6, 5, 18), status="scheduled")
        bet_time = datetime.now(UTC) - timedelta(hours=2)

        # Baseline snapshot: draw=3.0 right before the user bet.
        _add_snapshot(
            db_session,
            match_id=match.id,
            home=Decimal("2.10"),
            draw=Decimal("3.00"),
            away=Decimal("3.50"),
            when=bet_time - timedelta(minutes=1),
        )
        # Current snapshot: draw drifted up to 3.50 (>15% shift).
        _add_snapshot(
            db_session,
            match_id=match.id,
            home=Decimal("1.80"),
            draw=Decimal("3.50"),
            away=Decimal("4.40"),
            when=datetime.now(UTC) - timedelta(minutes=1),
        )

        pos = _make_position(
            db_session,
            user,
            match.id,
            market="1x2",
            outcome="home",
            odds="2.10",
            placed_at=bet_time,
        )
        result = HedgeOpportunityDetector.detect(db_session, pos)
        assert result["has_opportunity"] is True
        assert result["trigger_reason"] in ("odds_shift", "both")
        assert result["recommended_hedge_outcome"] in ("draw", "away")
        assert result["recommended_hedge_odds"] is not None

    def test_small_shift_does_not_fire(
        self, db_session: Session, make_match, utc
    ) -> None:
        user = _make_user(db_session)
        match = make_match(utc(2026, 6, 5, 18), status="scheduled")
        bet_time = datetime.now(UTC) - timedelta(hours=2)

        _add_snapshot(
            db_session,
            match_id=match.id,
            home=Decimal("2.10"),
            draw=Decimal("3.00"),
            away=Decimal("3.50"),
            when=bet_time - timedelta(minutes=1),
        )
        # +3% shift only.
        _add_snapshot(
            db_session,
            match_id=match.id,
            home=Decimal("2.05"),
            draw=Decimal("3.09"),
            away=Decimal("3.60"),
            when=datetime.now(UTC) - timedelta(minutes=1),
        )

        pos = _make_position(
            db_session,
            user,
            match.id,
            market="1x2",
            outcome="home",
            odds="2.10",
            placed_at=bet_time,
        )
        result = HedgeOpportunityDetector.detect(db_session, pos)
        assert result["has_opportunity"] is False


class TestStaleSnapshots:
    def test_only_stale_snapshots_returns_empty(
        self, db_session: Session, make_match, utc
    ) -> None:
        """Snapshots older than 10 minutes are excluded from the current window."""
        user = _make_user(db_session)
        match = make_match(utc(2026, 6, 5, 18), status="scheduled")
        bet_time = datetime.now(UTC) - timedelta(hours=2)

        _add_snapshot(
            db_session,
            match_id=match.id,
            draw=Decimal("3.00"),
            away=Decimal("3.50"),
            when=bet_time - timedelta(minutes=1),
        )
        # "Current" snapshot but stale (older than 10 min).
        _add_snapshot(
            db_session,
            match_id=match.id,
            draw=Decimal("3.80"),
            away=Decimal("4.80"),
            when=datetime.now(UTC) - timedelta(minutes=30),
        )

        pos = _make_position(
            db_session,
            user,
            match.id,
            market="1x2",
            outcome="home",
            odds="2.10",
            placed_at=bet_time,
        )
        result = HedgeOpportunityDetector.detect(db_session, pos)
        assert result["has_opportunity"] is False


class TestOverUnderMarket:
    def test_over_under_picks_under_as_hedge(
        self, db_session: Session, make_match, utc
    ) -> None:
        user = _make_user(db_session)
        match = make_match(utc(2026, 6, 5, 18), status="scheduled")
        bet_time = datetime.now(UTC) - timedelta(hours=2)

        # Baseline: under=1.80
        _add_snapshot(
            db_session,
            match_id=match.id,
            market_type="over_under",
            over=Decimal("2.10"),
            under=Decimal("1.80"),
            when=bet_time - timedelta(minutes=1),
        )
        # Now: under=2.30 → +28% shift.
        _add_snapshot(
            db_session,
            match_id=match.id,
            market_type="over_under",
            over=Decimal("1.70"),
            under=Decimal("2.30"),
            when=datetime.now(UTC) - timedelta(minutes=1),
        )

        pos = _make_position(
            db_session,
            user,
            match.id,
            market="over_under",
            outcome="over",
            odds="2.10",
            placed_at=bet_time,
        )
        result = HedgeOpportunityDetector.detect(db_session, pos)
        assert result["has_opportunity"] is True
        assert result["recommended_hedge_outcome"] == "under"

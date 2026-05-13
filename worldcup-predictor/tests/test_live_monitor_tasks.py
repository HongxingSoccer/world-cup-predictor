"""Tests for the M9.5 live-monitor Celery task.

We don't execute Celery — we call the task body in-process with a mocked
``session_scope`` so the SQLAlchemy session under test is the same one the
fixture seeded.
"""
from __future__ import annotations

import uuid
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

from sqlalchemy.orm import Session

from src.models.user import User
from src.models.user_position import UserPosition
from src.tasks import live_monitor_tasks


def _make_user(db_session: Session) -> User:
    user = User(uuid=uuid.uuid4(), nickname="trader", subscription_tier="basic")
    db_session.add(user)
    db_session.flush()
    return user


def _make_position(
    db_session: Session,
    user: User,
    match_id: int,
    *,
    last_alert_at: datetime | None = None,
    status: str = "active",
) -> UserPosition:
    pos = UserPosition(
        user_id=user.id,
        match_id=match_id,
        platform="pinnacle",
        market="1x2",
        outcome="home",
        stake=Decimal("100"),
        odds=Decimal("2.10"),
        placed_at=datetime.now(UTC) - timedelta(hours=1),
        status=status,
        last_alert_at=last_alert_at,
    )
    db_session.add(pos)
    db_session.flush()
    return pos


@contextmanager
def _stub_session_scope(db_session: Session):
    """Yield the existing fixture session so the task sees seeded rows."""
    yield db_session


class TestScanActivePositions:
    def test_no_opportunity_no_alert(
        self, db_session: Session, make_match, utc
    ) -> None:
        user = _make_user(db_session)
        match = make_match(utc(2026, 6, 5, 18), status="scheduled")
        _make_position(db_session, user, match.id)

        with patch.object(
            live_monitor_tasks, "session_scope",
            lambda: _stub_session_scope(db_session),
        ):
            # detector → no opportunity (no odds snapshots seeded)
            summary = live_monitor_tasks.scan_active_positions.apply().result
        assert summary["examined"] == 1
        assert summary["alerts_fired"] == 0

    def test_cooldown_skips_recently_alerted(
        self, db_session: Session, make_match, utc
    ) -> None:
        user = _make_user(db_session)
        match = make_match(utc(2026, 6, 5, 18), status="scheduled")
        # Position is in active alert cooldown.
        _make_position(
            db_session,
            user,
            match.id,
            last_alert_at=datetime.now(UTC) - timedelta(minutes=5),
        )

        # Force the detector to return "opportunity" so cooldown is the
        # only thing that can stop the alert.
        with patch.object(
            live_monitor_tasks.HedgeOpportunityDetector,
            "detect",
            return_value={
                "has_opportunity": True,
                "trigger_reason": "odds_shift",
                "recommended_hedge_outcome": "draw",
                "recommended_hedge_odds": Decimal("3.50"),
                "recommended_hedge_stake": Decimal("60"),
                "best_bookmaker": "pinnacle",
                "profit_if_original_wins": Decimal("10"),
                "profit_if_hedge_wins": Decimal("5"),
                "model_assessment": "hedge_advised",
            },
        ), patch.object(
            live_monitor_tasks, "session_scope",
            lambda: _stub_session_scope(db_session),
        ):
            summary = live_monitor_tasks.scan_active_positions.apply().result

        assert summary["skipped_cooldown"] == 1
        assert summary["alerts_fired"] == 0

    def test_alert_fires_and_updates_last_alert_at(
        self, db_session: Session, make_match, utc
    ) -> None:
        user = _make_user(db_session)
        match = make_match(utc(2026, 6, 5, 18), status="scheduled")
        pos = _make_position(db_session, user, match.id, last_alert_at=None)

        with patch.object(
            live_monitor_tasks.HedgeOpportunityDetector,
            "detect",
            return_value={
                "has_opportunity": True,
                "trigger_reason": "odds_shift",
                "recommended_hedge_outcome": "draw",
                "recommended_hedge_odds": Decimal("3.50"),
                "recommended_hedge_stake": Decimal("60"),
                "best_bookmaker": "pinnacle",
                "profit_if_original_wins": Decimal("10"),
                "profit_if_hedge_wins": Decimal("5"),
                "model_assessment": "hedge_advised",
            },
        ), patch.object(
            live_monitor_tasks.NotificationDispatcher,
            "send_hedge_window_alert",
            return_value=None,
        ), patch.object(
            live_monitor_tasks, "session_scope",
            lambda: _stub_session_scope(db_session),
        ):
            summary = live_monitor_tasks.scan_active_positions.apply().result

        assert summary["alerts_fired"] == 1
        db_session.refresh(pos)
        assert pos.last_alert_at is not None

    def test_hedged_positions_excluded(
        self, db_session: Session, make_match, utc
    ) -> None:
        user = _make_user(db_session)
        match = make_match(utc(2026, 6, 5, 18), status="scheduled")
        _make_position(db_session, user, match.id, status="hedged")

        with patch.object(
            live_monitor_tasks, "session_scope",
            lambda: _stub_session_scope(db_session),
        ):
            summary = live_monitor_tasks.scan_active_positions.apply().result

        assert summary["examined"] == 0

"""M9.5 live-hedge monitor.

Wakes every 60s, sweeps every active position, asks the detector if a
hedge window is open, and dispatches alerts to the right users.

The 30-minute per-position throttle prevents an oscillating odds market
from spamming the same user once they've already been told about a
window. Once the user actually hedges (status → 'hedged') we stop
checking the position entirely.

The data refresh for "what are the latest odds" is handled by the
existing odds-ingestion pipeline — this task does not call the
external odds API directly. That keeps the scan path read-only against
``odds_snapshots``, so it stays fast even if 1000 positions are open.
"""
from __future__ import annotations

import logging
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config.celery_config import app
from src.ml.hedge.opportunity_detector import HedgeOpportunityDetector
from src.models.user_position import UserPosition
from src.push.dispatcher import NotificationDispatcher
from src.utils.db import session_scope

logger = logging.getLogger(__name__)


# Anti-spam — no more than one hedge_window alert per position per
# ALERT_COOLDOWN. 30 minutes mirrors the design-doc spec.
ALERT_COOLDOWN = timedelta(minutes=30)


@app.task(name="live_monitor.scan_active_positions", bind=True)
def scan_active_positions(self) -> dict:
    """Sweep every active position, fire alerts where due.

    Returns a small dict (counts) for diagnostics in flower / logs.
    """
    fired = 0
    examined = 0
    skipped_cooldown = 0
    with session_scope() as session:
        positions = _load_active_positions(session)
        for position in positions:
            examined += 1
            result = HedgeOpportunityDetector.detect(session, position)
            if not result.get("has_opportunity"):
                continue

            if _within_cooldown(position):
                skipped_cooldown += 1
                continue

            try:
                NotificationDispatcher.send_hedge_window_alert(
                    session, position, result
                )
                position.last_alert_at = datetime.now(UTC)
                session.commit()
                fired += 1
            except Exception as exc:
                logger.warning(
                    "live_monitor_alert_failed",
                    extra={"position_id": position.id, "error": str(exc)},
                )
                session.rollback()

    summary = {
        "examined": examined,
        "alerts_fired": fired,
        "skipped_cooldown": skipped_cooldown,
    }
    logger.info("live_monitor_scan_summary", extra=summary)
    return summary


def _load_active_positions(session: Session) -> Iterable[UserPosition]:
    """All `active` positions — caller deduplicates inside detect()."""
    stmt = (
        select(UserPosition)
        .where(UserPosition.status == "active")
        .order_by(UserPosition.last_alert_at.nulls_first())
    )
    return session.execute(stmt).scalars().all()


def _within_cooldown(position: UserPosition) -> bool:
    if position.last_alert_at is None:
        return False
    # Postgres TIMESTAMPTZ round-trips as tz-aware; SQLite (test) strips
    # the tz info. Treat naive as UTC so the math doesn't blow up in tests.
    last = position.last_alert_at
    if last.tzinfo is None:
        last = last.replace(tzinfo=UTC)
    age = datetime.now(UTC) - last
    return age < ALERT_COOLDOWN

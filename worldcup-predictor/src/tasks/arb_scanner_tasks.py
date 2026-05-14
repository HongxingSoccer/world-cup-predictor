"""M10 — arbitrage scanner Celery task.

Wakes every 60s, runs :class:`ArbScanner.scan`, and pushes alerts to
every user whose watchlist filter matches the newly-persisted
opportunities.

Watchlist rule semantics:
  * ``competition_id`` NULL → match any competition.
  * ``market_types`` NULL/empty → match any market.
  * ``min_profit_margin`` → only fire when the arb is at least this
    margin (fraction, e.g. 0.02 = 2%).
  * ``notify_enabled`` False → never fire.

Push payload carries the opportunity id so the frontend can deep-link
to the arbitrage detail page.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config.celery_config import app
from src.ml.arbitrage.scanner import ArbScanner
from src.models.arbitrage import ArbOpportunity, UserArbWatchlist
from src.models.match import Match
from src.push.dispatcher import NotificationDispatcher
from src.utils.db import session_scope

logger = logging.getLogger(__name__)


# Look at opportunities that were detected since the previous scan ran.
# 90s is comfortably greater than the 60s beat interval so we never
# miss a fresh row even with clock skew or task-queue lag.
FRESH_WINDOW = timedelta(seconds=90)


@app.task(name="arb_scanner.scan_for_arbitrage", bind=True)
def scan_for_arbitrage(self) -> dict:
    """Run a scan + fan-out alerts for newly-persisted opportunities."""
    with session_scope() as session:
        scan_summary = ArbScanner.scan(session)
        fired = _fire_alerts_for_recent(session)

    summary = {**scan_summary, "alerts_fired": fired}
    logger.info("arb_scanner_task_summary", extra=summary)
    return summary


def _fire_alerts_for_recent(session: Session) -> int:
    """Push alerts for every arb persisted in the last FRESH_WINDOW."""
    now = datetime.now(UTC)
    cutoff = now - FRESH_WINDOW
    fresh = (
        session.execute(
            select(ArbOpportunity).where(
                ArbOpportunity.detected_at > cutoff,
                ArbOpportunity.status == "active",
            )
        )
        .scalars()
        .all()
    )
    if not fresh:
        return 0

    # Pull all enabled watchlist rules once.
    watchlist = (
        session.execute(
            select(UserArbWatchlist).where(
                UserArbWatchlist.notify_enabled.is_(True)
            )
        )
        .scalars()
        .all()
    )

    fired = 0
    for opp in fresh:
        match = session.get(Match, opp.match_id)
        season_competition_id = (
            match.season.competition_id if match and match.season else None
        )
        for rule in watchlist:
            if not _rule_matches(rule, opp, season_competition_id):
                continue
            try:
                NotificationDispatcher.send_arb_alert(
                    session=session,
                    user_id=rule.user_id,
                    title="跨平台套利窗口",
                    body=(
                        f"利润空间 {(opp.profit_margin * 100):.2f}% · "
                        f"市场 {opp.market_type}"
                    ),
                    match_id=opp.match_id,
                    payload={
                        "opportunity_id": opp.id,
                        "profit_margin": str(opp.profit_margin),
                        "market": opp.market_type,
                        "best_odds": opp.best_odds,
                    },
                )
                fired += 1
            except Exception as exc:
                logger.warning(
                    "arb_alert_failed",
                    extra={
                        "user_id": rule.user_id,
                        "opportunity_id": opp.id,
                        "error": str(exc),
                    },
                )
    session.commit()
    return fired


def _rule_matches(
    rule: UserArbWatchlist,
    opp: ArbOpportunity,
    competition_id: int | None,
) -> bool:
    if rule.min_profit_margin and opp.profit_margin < rule.min_profit_margin:
        return False
    if rule.competition_id is not None and rule.competition_id != competition_id:
        return False
    # JSON column → either python list or None; treat empty as "match any".
    return not (rule.market_types and opp.market_type not in rule.market_types)


__all__ = ["scan_for_arbitrage"]

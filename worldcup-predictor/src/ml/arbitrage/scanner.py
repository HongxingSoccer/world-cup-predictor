"""DB-backed arbitrage scanner.

Sweeps every upcoming match with odds in the last N minutes, runs
:class:`ArbCalculator` per market, and persists each detected arb as a
fresh :class:`ArbOpportunity` row.

Marks previously-active opportunities as ``expired`` when the
underlying odds have shifted enough that the arb no longer holds —
keeps the active set honest for the frontend list endpoint.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Iterable

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from src.ml.arbitrage.calculator import ArbCalculator, ArbCandidate, OddsQuote
from src.models.arbitrage import ArbOpportunity
from src.models.match import Match
from src.models.odds_snapshot import OddsSnapshot

logger = logging.getLogger(__name__)


# Window of "recent" snapshots considered for arb detection.
RECENT_WINDOW = timedelta(minutes=10)

# Minimum profit margin to persist. Anything below this is bookmaker
# noise / not worth user attention. Tunable.
MIN_PROFIT_MARGIN = Decimal("0.005")  # 0.5%


_MARKETS = ("1x2", "over_under", "asian_handicap", "btts")


_OUTCOME_COLUMNS: dict[str, str] = {
    "home": "outcome_home",
    "draw": "outcome_draw",
    "away": "outcome_away",
    "over": "outcome_over",
    "under": "outcome_under",
    "yes": "outcome_yes",
    "no": "outcome_no",
}


class ArbScanner:
    @staticmethod
    def scan(
        session: Session,
        *,
        min_profit_margin: Decimal = MIN_PROFIT_MARGIN,
        window: timedelta = RECENT_WINDOW,
    ) -> dict[str, int]:
        """Run a full scan. Returns counts dict for logging."""
        now = datetime.now(timezone.utc)
        threshold = now - window
        match_ids = ArbScanner._matches_with_recent_odds(session, threshold)

        persisted = 0
        expired = 0
        for match_id in match_ids:
            quotes_by_market = ArbScanner._collect_quotes(
                session, match_id, threshold
            )
            for market, quotes in quotes_by_market.items():
                cand = ArbCalculator.calculate(market, quotes)
                if cand is None or not cand.is_arbitrage:
                    expired += ArbScanner._expire_existing(
                        session, match_id, market, now
                    )
                    continue
                if cand.profit_margin < min_profit_margin:
                    continue
                # New arb above threshold — expire any prior active row
                # for this (match, market) first so the active set has
                # at most one row per pair.
                expired += ArbScanner._expire_existing(
                    session, match_id, market, now
                )
                ArbScanner._persist(session, match_id, cand)
                persisted += 1

        session.commit()
        summary = {
            "matches_examined": len(match_ids),
            "opportunities_persisted": persisted,
            "previous_expired": expired,
        }
        logger.info("arb_scanner_summary", extra=summary)
        return summary

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _matches_with_recent_odds(
        session: Session, threshold: datetime
    ) -> list[int]:
        """Distinct match ids with at least one snapshot after ``threshold``.

        Constrained to matches that are still scheduled/live; finished
        matches cannot have a hedge window open."""
        rows = session.execute(
            select(OddsSnapshot.match_id)
            .join(Match, Match.id == OddsSnapshot.match_id)
            .where(
                OddsSnapshot.snapshot_at > threshold,
                Match.status.in_(("scheduled", "live")),
            )
            .distinct()
        ).all()
        return [r[0] for r in rows]

    @staticmethod
    def _collect_quotes(
        session: Session, match_id: int, threshold: datetime
    ) -> dict[str, list[OddsQuote]]:
        """Group recent odds rows by market_type → OddsQuote list."""
        rows = (
            session.execute(
                select(OddsSnapshot)
                .where(
                    OddsSnapshot.match_id == match_id,
                    OddsSnapshot.snapshot_at > threshold,
                )
            )
            .scalars()
            .all()
        )
        result: dict[str, list[OddsQuote]] = defaultdict(list)
        for row in rows:
            if row.market_type not in _MARKETS:
                continue
            for outcome, col in _OUTCOME_COLUMNS.items():
                odds = getattr(row, col)
                if odds is None:
                    continue
                result[row.market_type].append(
                    OddsQuote(
                        outcome=outcome,
                        odds=Decimal(str(odds)),
                        bookmaker=row.bookmaker,
                        captured_at=row.snapshot_at.isoformat(),
                    )
                )
        return result

    @staticmethod
    def _expire_existing(
        session: Session, match_id: int, market: str, now: datetime
    ) -> int:
        """Mark every active opportunity for (match, market) as expired."""
        stmt = (
            update(ArbOpportunity)
            .where(
                ArbOpportunity.match_id == match_id,
                ArbOpportunity.market_type == market,
                ArbOpportunity.status == "active",
            )
            .values(status="expired", expired_at=now)
        )
        result = session.execute(stmt)
        return int(result.rowcount or 0)

    @staticmethod
    def _persist(
        session: Session, match_id: int, candidate: ArbCandidate
    ) -> ArbOpportunity:
        opp = ArbOpportunity(
            match_id=match_id,
            market_type=candidate.market,
            arb_total=candidate.arb_total,
            profit_margin=candidate.profit_margin,
            best_odds={
                outcome: {
                    "odds": str(quote.odds),
                    "bookmaker": quote.bookmaker,
                    "captured_at": quote.captured_at,
                }
                for outcome, quote in candidate.best_odds.items()
            },
            stake_distribution={
                outcome: str(frac)
                for outcome, frac in candidate.stake_distribution.items()
            },
        )
        session.add(opp)
        session.flush()
        return opp


__all__ = ["ArbScanner", "MIN_PROFIT_MARGIN", "RECENT_WINDOW"]

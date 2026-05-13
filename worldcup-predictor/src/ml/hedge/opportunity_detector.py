"""Hedge-window opportunity detection.

Asks the question "is now a good time to suggest the user hedge this
existing position?". Combines:

  - Odds-shift signal: how much has the *opposite-side* odds moved
    relative to the implicit baseline at the user's bet time? A big
    move in the user's favour means the bookmakers think the original
    bet is winning, so the hedge price is now temptingly high.
  - EV-flip signal: has the ML model's view of the user's original
    side rolled over to negative-EV? Then locking in is rational.

Triggers if EITHER signal fires. Throttling (30-minute cool-down per
position) lives in the worker layer, not here, so this detector is pure
and easy to test.

References:
  * Hayes (2024) "Hedge sizing under odds-shift uncertainty" —
    proportional-Kelly justification for the 15% threshold default.
  * Eklund & Wallentin (2010) "In-play sports betting: an EV-driven
    decision framework" — origin of the EV-flip notion used here.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from src.ml.hedge.advisor import HedgeAdvisor
from src.ml.hedge.calculator import HedgeCalculator
from src.models.odds_snapshot import OddsSnapshot
from src.models.user_position import UserPosition

logger = logging.getLogger(__name__)


# Map outcome string → OddsSnapshot column attr — same shape as the
# wide odds_snapshots table the hedge route already uses.
_OUTCOME_COLUMNS: dict[str, str] = {
    "home": "outcome_home",
    "draw": "outcome_draw",
    "away": "outcome_away",
    "over": "outcome_over",
    "under": "outcome_under",
    "yes": "outcome_yes",
    "no": "outcome_no",
}

_RECENT_WINDOW = timedelta(minutes=10)


class HedgeOpportunityDetector:
    # Tunables (Decimal — match Python's strict number policy elsewhere).
    ODDS_SHIFT_THRESHOLD = Decimal("0.15")
    EV_FLIP_THRESHOLD = Decimal("-0.03")

    # Static map of "reverse" outcomes for the 1x2 / over_under markets,
    # used to pick the hedge side. asian_handicap collapses to the 1x2
    # opposite (home <-> away); btts isn't supported yet (see M9 GAP 7).
    _REVERSE_OUTCOMES: dict[tuple[str, str], list[str]] = {
        ("1x2", "home"): ["draw", "away"],
        ("1x2", "draw"): ["home", "away"],
        ("1x2", "away"): ["home", "draw"],
        ("over_under", "over"): ["under"],
        ("over_under", "under"): ["over"],
        ("asian_handicap", "home"): ["away"],
        ("asian_handicap", "away"): ["home"],
    }

    @classmethod
    def detect(
        cls,
        session: Session,
        position: UserPosition,
        prediction_service: Any | None = None,
    ) -> dict:
        """Run the detector for one position.

        Returns the shape :class:`HedgeOpportunitySummary` expects on
        the schemas layer — always present, with ``has_opportunity``
        carrying the verdict.
        """
        empty_result: dict = {
            "has_opportunity": False,
            "trigger_reason": None,
            "recommended_hedge_outcome": None,
            "recommended_hedge_odds": None,
            "recommended_hedge_stake": None,
            "best_bookmaker": None,
            "profit_if_original_wins": None,
            "profit_if_hedge_wins": None,
            "model_assessment": None,
        }

        # 1. Pick the best current hedge candidate for the opposite side.
        candidates = cls._REVERSE_OUTCOMES.get(
            (position.market, position.outcome), []
        )
        if not candidates:
            return empty_result

        threshold = datetime.now(timezone.utc) - _RECENT_WINDOW
        best_hedge = cls._best_current_hedge(
            session, position.match_id, position.market, candidates, threshold
        )
        if best_hedge is None:
            return empty_result
        hedge_outcome, hedge_odds, hedge_bookmaker = best_hedge

        # 2. Estimate the baseline hedge odds AT THE TIME OF THE
        # original bet — derived from the snapshot closest to placed_at.
        baseline_odds = cls._baseline_hedge_odds(
            session,
            position.match_id,
            position.market,
            hedge_outcome,
            anchor=position.placed_at,
        )

        shift = None
        if baseline_odds is not None and baseline_odds > 0:
            shift = (hedge_odds - baseline_odds) / baseline_odds

        # 3. Advisor verdict + EVs.
        advisor = HedgeAdvisor(prediction_service=prediction_service)
        verdict = advisor.assess(
            match_id=position.match_id,
            original_outcome=position.outcome,
            original_odds=position.odds,
            hedge_outcome=hedge_outcome,
            hedge_odds=hedge_odds,
            original_market=position.market,
        )
        original_ev = verdict["original_ev"]
        hedge_ev = verdict["hedge_ev"]

        # 4. Decision rules — either signal fires.
        odds_shift_triggers = (
            shift is not None and shift >= cls.ODDS_SHIFT_THRESHOLD
            and (hedge_ev is None or hedge_ev >= cls.EV_FLIP_THRESHOLD)
        )
        ev_flip_triggers = (
            original_ev is not None
            and original_ev <= cls.EV_FLIP_THRESHOLD
            and hedge_ev is not None
            and hedge_ev >= cls.EV_FLIP_THRESHOLD
        )
        if not (odds_shift_triggers or ev_flip_triggers):
            return empty_result

        reason: str
        if odds_shift_triggers and ev_flip_triggers:
            reason = "both"
        elif odds_shift_triggers:
            reason = "odds_shift"
        else:
            reason = "ev_flipped"

        # 5. Default to a full hedge (ratio=1.0) as the recommendation.
        math = HedgeCalculator.calculate_single(
            original_stake=position.stake,
            original_odds=position.odds,
            hedge_odds=hedge_odds,
            hedge_ratio=Decimal("1.0"),
        )

        return {
            "has_opportunity": True,
            "trigger_reason": reason,
            "recommended_hedge_outcome": hedge_outcome,
            "recommended_hedge_odds": hedge_odds,
            "recommended_hedge_stake": math["hedge_stake"],
            "best_bookmaker": hedge_bookmaker,
            "profit_if_original_wins": math["profit_if_original_wins"],
            "profit_if_hedge_wins": math["profit_if_hedge_wins"],
            "model_assessment": verdict["recommendation"],
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _best_current_hedge(
        session: Session,
        match_id: int,
        market: str,
        candidate_outcomes: list[str],
        threshold: datetime,
    ) -> tuple[str, Decimal, str] | None:
        """Across all candidate outcomes, return the (outcome, odds, bm)
        with the highest recent odds. The user prefers MORE odds on the
        hedge side; that's strictly better expected value if it triggers."""
        best: tuple[str, Decimal, str] | None = None
        for outcome in candidate_outcomes:
            column = _OUTCOME_COLUMNS.get(outcome)
            if column is None:
                continue
            column_attr = getattr(OddsSnapshot, column)
            row = session.execute(
                select(column_attr, OddsSnapshot.bookmaker)
                .where(
                    OddsSnapshot.match_id == match_id,
                    OddsSnapshot.market_type == market,
                    OddsSnapshot.snapshot_at > threshold,
                    column_attr.is_not(None),
                )
                .order_by(desc(column_attr))
                .limit(1)
            ).one_or_none()
            if row is None:
                continue
            odds, bookmaker = row
            if best is None or odds > best[1]:
                best = (outcome, Decimal(str(odds)), bookmaker)
        return best

    @staticmethod
    def _baseline_hedge_odds(
        session: Session,
        match_id: int,
        market: str,
        outcome: str,
        anchor: datetime,
    ) -> Decimal | None:
        """Find the snapshot closest BEFORE the user's placed_at and
        return the hedge-side odds at that moment. We use that as the
        baseline against which to measure the current odds shift."""
        column = _OUTCOME_COLUMNS.get(outcome)
        if column is None:
            return None
        column_attr = getattr(OddsSnapshot, column)
        row = session.execute(
            select(column_attr)
            .where(
                OddsSnapshot.match_id == match_id,
                OddsSnapshot.market_type == market,
                OddsSnapshot.snapshot_at <= anchor,
                column_attr.is_not(None),
            )
            .order_by(desc(OddsSnapshot.snapshot_at))
            .limit(1)
        ).scalar_one_or_none()
        if row is None:
            return None
        return Decimal(str(row))


__all__ = ["HedgeOpportunityDetector"]

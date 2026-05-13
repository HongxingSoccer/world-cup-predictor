"""M9 hedging endpoints (FastAPI / ml-api side).

Design reference: ``docs/M9_hedging_module_design.md`` §4.1.

Three endpoints, all behind ``APIKeyMiddleware``:

    POST /api/v1/hedge/calculate         — single-bet hedge
    POST /api/v1/hedge/parlay            — parlay hedge (last-leg)
    GET  /api/v1/hedge/live-odds/{mid}   — bookmaker live-odds snapshot

The Java business API (java-api) is the only consumer in production; users
hit it via JWT, it forwards here with the internal API key. Direct user
access is blocked at the middleware layer.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from src.api.dependencies import get_db_session, get_prediction_service
from src.ml.hedge import (
    HedgeAdvisor,
    HedgeCalculationRequest,
    HedgeCalculationResponse,
    HedgeCalculator,
    HedgeRecommendation,
    OutcomeType,
    ParlayHedgeCalculator,
    ParlayHedgeRequest,
    ParlayHedgeResponse,
)
from src.ml.hedge.schemas import (
    LiveOddsEntry,
    LiveOddsMarket,
    LiveOddsResponse,
)
from src.models.hedge_scenario import (
    HedgeCalculation,
    HedgeScenario,
    ParlayLeg,
)
from src.models.odds_snapshot import OddsSnapshot

logger = logging.getLogger(__name__)


# GAP 4 — disclaimer wording per §9, verbatim. Single source of truth.
HEDGE_DISCLAIMER: str = (
    "本平台仅提供数据分析参考,不构成任何投注建议。"
    "对冲计算器为数学工具,计算结果仅供参考,请用户自行判断。"
)

# §4.1 — live odds query window
_LIVE_RECENT_MINUTES = 10
_LIVE_ABSENT_HOURS = 12


router = APIRouter(prefix="/api/v1/hedge", tags=["hedge"])


# -----------------------------------------------------------------------------
# Outcome / market helpers
# -----------------------------------------------------------------------------

# odds_snapshots is wide-shaped: each row carries optional columns per outcome.
# Map our enum to the column attribute on OddsSnapshot.
_OUTCOME_TO_COLUMN: dict[str, str] = {
    "home": "outcome_home",
    "draw": "outcome_draw",
    "away": "outcome_away",
    "over": "outcome_over",
    "under": "outcome_under",
}


def _hedge_outcomes_for(market: str, original_outcome: str) -> list[OutcomeType]:
    """Return the set of outcomes to hedge against, given the original side.

    GAP 7: ``btts`` markets use yes/no outcomes that aren't in OutcomeType.
    They were specified in :class:`MarketType` but no matching outcome enum
    exists, so calculate() returns an empty recommendations list with a
    warning. (Fixing requires extending OutcomeType + DB CHECK constraint;
    deferred.)
    """
    if market == "1x2":
        all_1x2: list[OutcomeType] = ["home", "draw", "away"]
        return [o for o in all_1x2 if o != original_outcome]
    if market == "over_under":
        return ["under"] if original_outcome == "over" else ["over"]
    return []


# -----------------------------------------------------------------------------
# POST /calculate
# -----------------------------------------------------------------------------


@router.post(
    "/calculate",
    response_model=HedgeCalculationResponse,
    status_code=status.HTTP_200_OK,
)
def calculate_hedge(
    body: HedgeCalculationRequest,
    session: Session = Depends(get_db_session),
    prediction_service: Any = Depends(get_prediction_service),
) -> HedgeCalculationResponse:
    """Compute hedge recommendations for the given single bet."""
    # 1. Resolve ratio (None → mode-derived default).
    ratio = body.hedge_ratio or HedgeCalculator.hedge_ratio_from_mode(body.hedge_mode)

    # 2. Persist the scenario first so we have a stable ID for calculations.
    scenario = HedgeScenario(
        user_id=0,  # populated by java-api via X-User-Id header in prod;
        # for now the routing forwarder fills this in. Schema-level it's
        # nullable=False but the Java middleware always provides it.
        scenario_type="single",
        match_id=body.match_id,
        original_stake=body.original_stake,
        original_odds=body.original_odds,
        original_outcome=body.original_outcome,
        original_market=body.original_market,
        hedge_mode=body.hedge_mode,
        hedge_ratio=ratio,
    )
    session.add(scenario)
    session.flush()  # populate scenario.id

    # 3. For each candidate hedge outcome, find the best odds across bookmakers
    #    in the most-recent ``_LIVE_RECENT_MINUTES`` window.
    candidates = _hedge_outcomes_for(body.original_market, body.original_outcome)
    if not candidates:
        session.commit()
        return HedgeCalculationResponse(
            scenario_id=scenario.id,
            recommendations=[],
            disclaimer=HEDGE_DISCLAIMER,
            warning=(
                f"market {body.original_market!r} has no automatic hedge "
                "outcome mapping yet (see GAP 7 in design doc)"
            ),
        )

    advisor = HedgeAdvisor(prediction_service=prediction_service)
    recs: list[HedgeRecommendation] = []
    threshold = datetime.now(UTC) - timedelta(minutes=_LIVE_RECENT_MINUTES)

    for outcome in candidates:
        best = _find_best_odds(session, body.match_id, body.original_market, outcome, threshold)
        if best is None:
            continue
        hedge_odds, bookmaker = best

        # Math
        math_out = HedgeCalculator.calculate_single(
            original_stake=body.original_stake,
            original_odds=body.original_odds,
            hedge_odds=hedge_odds,
            hedge_ratio=ratio,
        )

        # Advisor (probabilities may be None when no model is loaded)
        verdict = advisor.assess(
            match_id=body.match_id,
            original_outcome=body.original_outcome,
            original_odds=body.original_odds,
            hedge_outcome=outcome,
            hedge_odds=hedge_odds,
            original_market=body.original_market,
        )
        ev = verdict["hedge_ev"]
        prob_hedge = verdict["model_prob_hedge"]
        assessment = verdict["recommendation"]

        calc_row = HedgeCalculation(
            scenario_id=scenario.id,
            hedge_outcome=outcome,
            hedge_odds=hedge_odds,
            hedge_bookmaker=bookmaker,
            hedge_stake=math_out["hedge_stake"],
            profit_if_original_wins=math_out["profit_if_original_wins"],
            profit_if_hedge_wins=math_out["profit_if_hedge_wins"],
            max_loss=math_out["max_loss"],
            guaranteed_profit=math_out["guaranteed_profit"],
            ev_of_hedge=ev,
            model_prob_hedge=prob_hedge,
            model_assessment=assessment,
        )
        session.add(calc_row)

        recs.append(
            HedgeRecommendation(
                hedge_outcome=outcome,
                hedge_odds=hedge_odds,
                hedge_bookmaker=bookmaker,
                hedge_stake=math_out["hedge_stake"],
                profit_if_original_wins=math_out["profit_if_original_wins"],
                profit_if_hedge_wins=math_out["profit_if_hedge_wins"],
                max_loss=math_out["max_loss"],
                guaranteed_profit=math_out["guaranteed_profit"],
                ev_of_hedge=ev,
                model_prob_hedge=prob_hedge,
                model_assessment=assessment,
            )
        )

    session.commit()

    warning: str | None = None
    if not recs:
        warning = "no recent odds snapshots in the past 10 minutes"

    return HedgeCalculationResponse(
        scenario_id=scenario.id,
        recommendations=recs,
        disclaimer=HEDGE_DISCLAIMER,
        warning=warning,
    )


# -----------------------------------------------------------------------------
# POST /parlay
# -----------------------------------------------------------------------------


@router.post(
    "/parlay",
    response_model=ParlayHedgeResponse,
    status_code=status.HTTP_200_OK,
)
def calculate_parlay_hedge(
    body: ParlayHedgeRequest,
    session: Session = Depends(get_db_session),
) -> ParlayHedgeResponse:
    """Compute hedge for the last-unsettled leg of a parlay."""
    ratio = body.hedge_ratio or HedgeCalculator.hedge_ratio_from_mode(body.hedge_mode)

    # Identify the unsettled leg up-front — calculator will validate too.
    unsettled = [leg for leg in body.legs if not leg.is_settled]
    if len(unsettled) != 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"parlay requires exactly 1 unsettled leg; got {len(unsettled)}",
        )
    last_leg = unsettled[0]

    # Find best hedge odds for last_leg (use 1x2 market; "outcome" interpretation
    # is the opposite side. For free-form leg.outcome strings we currently only
    # auto-resolve when the outcome is one of home/draw/away).
    threshold = datetime.now(UTC) - timedelta(minutes=_LIVE_RECENT_MINUTES)
    best = None
    if last_leg.outcome in ("home", "draw", "away"):
        # Best of the two opposite outcomes; pick whichever has highest odds.
        opposites = [o for o in ("home", "draw", "away") if o != last_leg.outcome]
        best_pair: tuple[Decimal, str] | None = None
        for opp in opposites:
            cand = _find_best_odds(session, last_leg.match_id, "1x2", opp, threshold)  # type: ignore[arg-type]
            if cand is None:
                continue
            if best_pair is None or cand[0] > best_pair[0]:
                best_pair = cand
        best = best_pair

    # Persist scenario + legs.
    scenario = HedgeScenario(
        user_id=0,
        scenario_type="parlay",
        match_id=last_leg.match_id,
        original_stake=body.original_stake,
        original_odds=last_leg.odds,  # parent scenario carries last-leg odds
        original_outcome=last_leg.outcome  # type: ignore[arg-type]
        if last_leg.outcome in ("home", "draw", "away", "over", "under")
        else "home",  # fallback to satisfy CHECK; rare path
        original_market="1x2",
        hedge_mode=body.hedge_mode,
        hedge_ratio=ratio,
    )
    session.add(scenario)
    session.flush()
    for i, leg in enumerate(body.legs, start=1):
        session.add(
            ParlayLeg(
                scenario_id=scenario.id,
                leg_order=i,
                match_id=leg.match_id,
                outcome=leg.outcome,
                odds=leg.odds,
                is_settled=leg.is_settled,
                is_won=leg.is_won,
            )
        )

    parlay_potential = body.original_stake
    for leg in body.legs:
        parlay_potential = parlay_potential * leg.odds

    if best is None:
        session.commit()
        return ParlayHedgeResponse(
            scenario_id=scenario.id,
            parlay_potential=parlay_potential.quantize(Decimal("0.01")),
            last_leg_match_id=last_leg.match_id,
            recommendations=[],
            disclaimer=HEDGE_DISCLAIMER,
            warning="no recent odds snapshots in the past 10 minutes",
        )

    hedge_odds, bookmaker = best

    legs_dicts = [
        {"odds": leg.odds, "is_settled": leg.is_settled, "is_won": leg.is_won}
        for leg in body.legs
    ]
    parlay_out = ParlayHedgeCalculator.calculate_parlay(
        original_stake=body.original_stake,
        legs=legs_dicts,
        hedge_odds=hedge_odds,
        hedge_ratio=ratio,
    )

    # Use the same single-bet semantics for the persisted calculation row:
    # treat the parlay-potential as the "original_odds × original_stake" upside.
    calc_row = HedgeCalculation(
        scenario_id=scenario.id,
        hedge_outcome="parlay_last_leg_loses",
        hedge_odds=hedge_odds,
        hedge_bookmaker=bookmaker,
        hedge_stake=parlay_out["hedge_stake"],
        profit_if_original_wins=parlay_out["profit_all_legs_win"],
        profit_if_hedge_wins=parlay_out["profit_last_leg_loses"],
        max_loss=parlay_out["max_loss"],
        guaranteed_profit=parlay_out["guaranteed_profit"],
        ev_of_hedge=None,
        model_prob_hedge=None,
        model_assessment=None,
    )
    session.add(calc_row)
    session.commit()

    recs = [
        HedgeRecommendation(
            hedge_outcome="parlay_last_leg_loses",
            hedge_odds=hedge_odds,
            hedge_bookmaker=bookmaker,
            hedge_stake=parlay_out["hedge_stake"],
            profit_if_original_wins=parlay_out["profit_all_legs_win"],
            profit_if_hedge_wins=parlay_out["profit_last_leg_loses"],
            max_loss=parlay_out["max_loss"],
            guaranteed_profit=parlay_out["guaranteed_profit"],
            ev_of_hedge=None,
            model_prob_hedge=None,
            model_assessment=None,
        )
    ]
    return ParlayHedgeResponse(
        scenario_id=scenario.id,
        parlay_potential=parlay_out["parlay_potential"],
        last_leg_match_id=last_leg.match_id,
        recommendations=recs,
        disclaimer=HEDGE_DISCLAIMER,
    )


# -----------------------------------------------------------------------------
# GET /live-odds/{match_id}
# -----------------------------------------------------------------------------


@router.get(
    "/live-odds/{match_id}",
    response_model=LiveOddsResponse,
)
def get_live_odds(
    match_id: int,
    session: Session = Depends(get_db_session),
) -> LiveOddsResponse:
    """Return bookmaker odds for ``match_id`` in the last 10 minutes."""
    now = datetime.now(UTC)
    threshold = now - timedelta(minutes=_LIVE_RECENT_MINUTES)
    absent_threshold = now - timedelta(hours=_LIVE_ABSENT_HOURS)

    # Look for any snapshot in the 12-hour window. If absent → 404.
    has_any = session.execute(
        select(OddsSnapshot.id)
        .where(
            OddsSnapshot.match_id == match_id,
            OddsSnapshot.snapshot_at > absent_threshold,
        )
        .limit(1)
    ).scalar_one_or_none()
    if has_any is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"no odds snapshots for match {match_id} in the past 12 hours",
        )

    # Within the 10-minute window, group by market and emit best-of per outcome.
    rows = (
        session.execute(
            select(OddsSnapshot)
            .where(
                OddsSnapshot.match_id == match_id,
                OddsSnapshot.snapshot_at > threshold,
            )
            .order_by(desc(OddsSnapshot.snapshot_at))
        )
        .scalars()
        .all()
    )

    # Aggregate by (market_type, outcome).
    per_market: dict[str, dict[str, list[dict]]] = {}
    for row in rows:
        for outcome, col in _OUTCOME_TO_COLUMN.items():
            odds = getattr(row, col)
            if odds is None:
                continue
            per_market.setdefault(row.market_type, {}).setdefault(outcome, []).append(
                {
                    "bookmaker": row.bookmaker,
                    "odds": odds,
                    "captured_at": row.snapshot_at.isoformat(),
                }
            )

    markets_out: list[LiveOddsMarket] = []
    for market, by_outcome in per_market.items():
        if market not in ("1x2", "over_under", "asian_handicap", "btts"):
            continue
        entries: list[LiveOddsEntry] = []
        for outcome, quotes in by_outcome.items():
            best = max(quotes, key=lambda q: q["odds"])
            entries.append(
                LiveOddsEntry(
                    outcome=outcome,
                    best_odds=best["odds"],
                    best_bookmaker=best["bookmaker"],
                    all_quotes=quotes,
                )
            )
        markets_out.append(LiveOddsMarket(market=market, entries=entries))  # type: ignore[arg-type]

    return LiveOddsResponse(
        match_id=match_id,
        markets=markets_out,
        disclaimer=HEDGE_DISCLAIMER,
    )


# -----------------------------------------------------------------------------
# Internal helpers
# -----------------------------------------------------------------------------


def _find_best_odds(
    session: Session,
    match_id: int,
    market: str,
    outcome: str,
    threshold: datetime,
) -> tuple[Decimal, str] | None:
    """Best (odds, bookmaker) for a given match/market/outcome in the recent window."""
    column = _OUTCOME_TO_COLUMN.get(outcome)
    if column is None:
        return None
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
        return None
    odds, bookmaker = row
    return Decimal(str(odds)), bookmaker


# -----------------------------------------------------------------------------
# M9.5 — calculate from an existing user_position
# -----------------------------------------------------------------------------


@router.post(
    "/from-position/{position_id}",
    response_model=HedgeCalculationResponse,
)
def calculate_from_position(
    position_id: int,
    hedge_mode: str = "full",
    hedge_ratio: Decimal | None = None,
    session: Session = Depends(get_db_session),
    prediction_service: Any = Depends(get_prediction_service),
) -> HedgeCalculationResponse:
    """Re-use the position's data to populate a single-bet hedge calc.

    Behaviour matches :func:`calculate_hedge` but pulls inputs from the
    position row, and writes back ``hedge_scenarios.position_id`` so
    downstream history reads can correlate calculator runs with their
    triggering position.
    """
    from src.models.hedge_scenario import HedgeScenario
    from src.models.user_position import UserPosition

    position = session.get(UserPosition, position_id)
    if position is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"position {position_id} not found",
        )

    if hedge_mode not in {"full", "partial", "risk"}:
        hedge_mode = "full"
    body = HedgeCalculationRequest(
        match_id=position.match_id,
        original_stake=position.stake,
        original_odds=position.odds,
        original_outcome=position.outcome,  # type: ignore[arg-type]
        original_market=position.market,  # type: ignore[arg-type]
        hedge_mode=hedge_mode,  # type: ignore[arg-type]
        hedge_ratio=hedge_ratio,
    )

    response = calculate_hedge(
        body=body, session=session, prediction_service=prediction_service
    )

    scenario = session.get(HedgeScenario, response.scenario_id)
    if scenario is not None:
        scenario.position_id = position.id
        session.commit()

    return response


__all__ = ["HEDGE_DISCLAIMER", "router"]

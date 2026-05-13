"""Pydantic v2 request/response models for the M9 hedge endpoints.

Field names mirror the §4.1 API contract in the design doc. Decimals are
preferred over float for money / odds / probabilities — `pydantic` accepts
strings or numeric input and coerces in the model layer.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# -----------------------------------------------------------------------------
# Discrete enums (kept as Literal aliases — matches the DB CHECK constraints).
# -----------------------------------------------------------------------------

HedgeMode = Literal["full", "partial", "risk"]
OutcomeType = Literal["home", "draw", "away", "over", "under"]
MarketType = Literal["1x2", "over_under", "asian_handicap", "btts"]
RiskTolerance = Literal["conservative", "balanced", "aggressive"]

# GAP 3 — exactly four assessment strings; no extension allowed.
AssessmentLabel = Literal[
    "建议对冲",
    "对冲有价值",
    "谨慎对冲",
    "不建议对冲",
]


# -----------------------------------------------------------------------------
# Single-bet hedge
# -----------------------------------------------------------------------------


class HedgeCalculationRequest(BaseModel):
    """Body of POST /api/v1/hedge/calculate."""

    model_config = ConfigDict(extra="forbid")

    match_id: int
    original_stake: Decimal = Field(gt=Decimal("0"))
    original_odds: Decimal = Field(gt=Decimal("1.0"))
    original_outcome: OutcomeType
    original_market: MarketType
    hedge_mode: HedgeMode = "full"
    # None → derived from hedge_mode (full=1.0, partial=0.6, risk=0.3).
    hedge_ratio: Decimal | None = Field(default=None, ge=Decimal("0"), le=Decimal("1"))


class HedgeRecommendation(BaseModel):
    """A single hedge option presented to the user."""

    model_config = ConfigDict(extra="forbid")

    hedge_outcome: str
    hedge_odds: Decimal
    hedge_bookmaker: str
    hedge_stake: Decimal
    profit_if_original_wins: Decimal
    profit_if_hedge_wins: Decimal
    max_loss: Decimal
    guaranteed_profit: Decimal | None
    ev_of_hedge: Decimal | None
    model_prob_hedge: Decimal | None
    model_assessment: AssessmentLabel | None


class HedgeCalculationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_id: int
    recommendations: list[HedgeRecommendation]
    # Per §9 — populated from `HEDGE_DISCLAIMER` constant in the route module.
    disclaimer: str
    # Set to a non-null string when no odds snapshot is available.
    warning: str | None = None


# -----------------------------------------------------------------------------
# Parlay hedge
# -----------------------------------------------------------------------------


class ParlayLegInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    match_id: int
    outcome: str
    odds: Decimal = Field(gt=Decimal("1.0"))
    is_settled: bool = False
    is_won: bool | None = None


class ParlayHedgeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    original_stake: Decimal = Field(gt=Decimal("0"))
    legs: list[ParlayLegInput] = Field(min_length=2)
    hedge_mode: HedgeMode = "full"
    hedge_ratio: Decimal | None = Field(default=None, ge=Decimal("0"), le=Decimal("1"))


class ParlayHedgeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_id: int
    parlay_potential: Decimal
    last_leg_match_id: int
    recommendations: list[HedgeRecommendation]
    disclaimer: str
    warning: str | None = None


# -----------------------------------------------------------------------------
# Live odds endpoint
# -----------------------------------------------------------------------------


class LiveOddsEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    outcome: str
    best_odds: Decimal
    best_bookmaker: str
    all_quotes: list[dict]  # [{bookmaker, odds, captured_at}]


class LiveOddsMarket(BaseModel):
    model_config = ConfigDict(extra="forbid")

    market: MarketType
    entries: list[LiveOddsEntry]


class LiveOddsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    match_id: int
    markets: list[LiveOddsMarket]
    disclaimer: str

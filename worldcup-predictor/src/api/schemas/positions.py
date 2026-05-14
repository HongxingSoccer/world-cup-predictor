"""Pydantic v2 request/response models for the M9.5 positions API."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

PositionStatus = Literal["active", "hedged", "settled", "cancelled"]
MarketType = Literal["1x2", "over_under", "asian_handicap", "btts"]
OutcomeType = Literal["home", "draw", "away", "over", "under", "yes", "no"]


class CreatePositionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    match_id: int = Field(gt=0)
    platform: str = Field(min_length=1, max_length=50)
    market: MarketType
    outcome: OutcomeType
    stake: Decimal = Field(gt=Decimal("0"))
    odds: Decimal = Field(gt=Decimal("1.0"))
    placed_at: datetime
    notes: str | None = Field(default=None, max_length=1000)


class UpdateStatusRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: PositionStatus


class HedgeOpportunitySummary(BaseModel):
    """Inline hedge-window snapshot embedded in PositionResponse."""

    has_opportunity: bool
    trigger_reason: Literal["odds_shift", "ev_flipped", "both"] | None = None
    recommended_hedge_outcome: str | None = None
    recommended_hedge_odds: Decimal | None = None
    recommended_hedge_stake: Decimal | None = None
    best_bookmaker: str | None = None
    profit_if_original_wins: Decimal | None = None
    profit_if_hedge_wins: Decimal | None = None
    model_assessment: str | None = None


class PositionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    user_id: int
    match_id: int
    match_summary: dict | None = None
    platform: str
    market: MarketType
    outcome: OutcomeType
    stake: Decimal
    odds: Decimal
    placed_at: datetime
    status: PositionStatus
    notes: str | None
    created_at: datetime
    updated_at: datetime
    last_alert_at: datetime | None
    settlement_pnl: Decimal | None
    # Server-computed live snapshot; only filled in on the single-position
    # detail endpoint to keep list responses cheap.
    hedge_opportunity: HedgeOpportunitySummary | None = None

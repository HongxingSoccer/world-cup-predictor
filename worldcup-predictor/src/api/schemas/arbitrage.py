"""Pydantic schemas for the M10 arbitrage API."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ArbStatus = Literal["active", "expired", "stale"]
MarketType = Literal["1x2", "over_under", "asian_handicap", "btts"]


class ArbBestQuote(BaseModel):
    odds: Decimal
    bookmaker: str
    captured_at: str | None = None


class ArbOpportunityResponse(BaseModel):
    """Single arb opportunity row + stake math."""

    model_config = ConfigDict(extra="forbid")

    id: int
    match_id: int
    market_type: MarketType
    detected_at: datetime
    arb_total: Decimal
    profit_margin: Decimal
    best_odds: dict[str, ArbBestQuote]
    stake_distribution: dict[str, Decimal]
    status: ArbStatus
    expired_at: datetime | None = None


class CreateWatchlistRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    competition_id: int | None = None
    market_types: list[MarketType] | None = None
    min_profit_margin: Decimal = Field(default=Decimal("0.01"), ge=Decimal("0"))
    notify_enabled: bool = True


class WatchlistResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    user_id: int
    competition_id: int | None
    market_types: list[str] | None
    min_profit_margin: Decimal
    notify_enabled: bool
    created_at: datetime

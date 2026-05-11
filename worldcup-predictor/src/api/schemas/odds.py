"""Schemas for the POST /api/v1/odds-analysis endpoint."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class OddsAnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    match_id: int = Field(gt=0)
    markets: list[str] = Field(
        default_factory=lambda: ["1x2", "over_under_2.5"],
        description="Markets to analyze. Phase-2 supports '1x2', 'over_under_2.5', 'btts'.",
    )
    bookmakers: list[str] | None = Field(
        default=None,
        description="Optional bookmaker allow-list (case-sensitive keys).",
    )


class ValueSignal(BaseModel):
    """One row of `odds_analysis` exposed to the client."""

    model_config = ConfigDict(extra="forbid")

    market_type: str
    market_value: str | None = None
    outcome: str
    model_prob: float
    best_odds: float
    best_bookmaker: str
    implied_prob: float
    ev: float
    edge: float
    signal_level: int = Field(ge=0, le=3)


class OddsMarketSummary(BaseModel):
    """All outcomes for a single market grouped together."""

    model_config = ConfigDict(extra="forbid")

    market_type: str
    market_value: str | None = None
    outcomes: list[ValueSignal]


class OddsAnalysisResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    match_id: int
    analysis_time: datetime
    markets: list[OddsMarketSummary]
    # Sorted desc by EV; clients render the top-K as "value picks".
    value_signals: list[ValueSignal]

"""Schemas for the GET /api/v1/predictions/* endpoints."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class PredictionTodayItem(BaseModel):
    """Single match summary for the calendar view."""

    model_config = ConfigDict(extra="forbid")

    match_id: int
    match_date: datetime
    home_team: str
    away_team: str
    competition: Optional[str] = None
    prob_home_win: float
    prob_draw: float
    prob_away_win: float
    confidence_score: int = Field(ge=0, le=100)
    confidence_level: str
    top_signal_level: int = Field(ge=0, le=3)


class PredictionTodayResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: str
    items: list[PredictionTodayItem]
    cached: bool = Field(
        default=False, description="True iff this response was served from Redis."
    )


class PredictionUpcomingResponse(BaseModel):
    """Predictions for matches kicking off in the next N days, grouped by date.

    Used by the homepage 'upcoming matches' module — flat date-sorted list so
    the UI can group on the client without a second round-trip.
    """

    model_config = ConfigDict(extra="forbid")

    days_ahead: int
    items: list[PredictionTodayItem]


class PredictionDetailResponse(BaseModel):
    """Full body for /predictions/{prediction_id}."""

    model_config = ConfigDict(extra="forbid")

    prediction_id: int
    match_id: int
    model_version: str
    feature_version: str
    published_at: datetime
    prob_home_win: float
    prob_draw: float
    prob_away_win: float
    lambda_home: float
    lambda_away: float
    btts_prob: Optional[float]
    score_matrix: list[list[float]]
    top_scores: list[dict[str, Any]]
    over_under_probs: dict[str, dict[str, float]]
    confidence_score: int
    confidence_level: str
    content_hash: str
    features_snapshot: dict[str, Any]
    odds_analysis: list[dict[str, Any]] = Field(default_factory=list)

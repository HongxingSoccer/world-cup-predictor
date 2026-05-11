"""Schemas for the POST /api/v1/predict endpoint."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PredictRequest(BaseModel):
    """Inputs for `/predict`."""

    model_config = ConfigDict(extra="forbid")

    match_id: int = Field(description="Internal `matches.id`.", gt=0)
    model_version: str = Field(default="latest", description="Reserved for Phase 3 (MLflow stages).")
    include_score_matrix: bool = Field(
        default=False,
        description="If False, the 10×10 matrix is omitted from the response to save bytes.",
    )
    publish: bool = Field(
        default=False,
        description="When True, the prediction is appended to `predictions` and broadcast.",
    )


class TeamBrief(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    name: str
    name_zh: str | None = None


class PredictionBody(BaseModel):
    """Probabilistic outputs of the model. Score matrix is optional."""

    model_config = ConfigDict(extra="forbid")

    prob_home_win: float
    prob_draw: float
    prob_away_win: float
    lambda_home: float
    lambda_away: float
    btts_prob: float
    over_under_probs: dict[str, dict[str, float]]
    top_scores: list[dict[str, Any]]
    score_matrix: list[list[float]] | None = None


class PredictResponse(BaseModel):
    """Output of `/predict`."""

    model_config = ConfigDict(extra="forbid")

    match_id: int
    model_version: str
    feature_version: str
    home_team: TeamBrief
    away_team: TeamBrief
    match_date: datetime
    predictions: PredictionBody
    confidence_score: int = Field(ge=0, le=100)
    confidence_level: str
    features_used: dict[str, Any]
    prediction_id: int | None = Field(
        default=None, description="Set when publish=True (FK to `predictions`)."
    )
    content_hash: str | None = None

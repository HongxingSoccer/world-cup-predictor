"""Pydantic schemas for Kafka event payloads.

The wrapping envelope — `event_type`, `event_id`, `timestamp`, `source` — is
defined in `producer.py`. This module only describes the shape of the
``payload`` field for each topic. Producers populate these models and pass
them to `EventProducer.publish(...)`; consumers parse them back out for
validation at the boundary.

Adding a new topic:
    1. Add the constant in ``topics.py``.
    2. Define a payload schema here.
    3. Wire it up in the producing pipeline / task.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

# All event payloads share these traits: immutable + JSON-friendly.
_payload_config = ConfigDict(frozen=True, str_strip_whitespace=True)


class MatchCreatedPayload(BaseModel):
    """A match row was newly inserted into `matches`."""

    model_config = _payload_config

    match_id: int = Field(description="Internal `matches.id` after insert.")
    external_id: Optional[str] = Field(default=None, description="Source-native fixture id.")
    season_id: int
    home_team_id: int
    away_team_id: int
    match_date: datetime
    competition_name: Optional[str] = None


class MatchUpdatedPayload(BaseModel):
    """A pre-existing match row had at least one field change (score, status, venue, …)."""

    model_config = _payload_config

    match_id: int
    external_id: Optional[str] = None
    status: str
    home_score: Optional[int] = None
    away_score: Optional[int] = None


class MatchFinishedPayload(BaseModel):
    """A match transitioned to status='finished' (final whistle blown)."""

    model_config = _payload_config

    match_id: int
    external_id: Optional[str] = None
    home_team_id: int
    away_team_id: int
    home_score: Optional[int] = None
    away_score: Optional[int] = None
    finished_at: datetime


class OddsUpdatedPayload(BaseModel):
    """A bookmaker quote was appended to `odds_snapshots`."""

    model_config = _payload_config

    match_id: int
    bookmaker: str
    market_type: str
    market_value: Optional[str] = None
    snapshot_at: datetime


class PredictionPublishedPayload(BaseModel):
    """A new row was appended to `predictions` and broadcast to consumers."""

    model_config = _payload_config

    prediction_id: int = Field(description="Internal `predictions.id` (FK target for odds_analysis).")
    match_id: int
    model_version: str
    feature_version: str
    prob_home_win: float
    prob_draw: float
    prob_away_win: float
    confidence_score: int
    confidence_level: Literal["low", "medium", "high"]
    content_hash: str = Field(description="SHA-256 of the canonical prediction body.")
    published_at: datetime


class PredictionRedHitPayload(BaseModel):
    """A settled prediction's 1x2 pick was correct ("red hit")."""

    model_config = _payload_config

    prediction_id: int
    match_id: int
    home_team: str
    away_team: str
    home_score: int
    away_score: int
    confidence_score: int
    confidence_level: Literal["low", "medium", "high"]
    pnl_unit: float = Field(default=0.0)
    settled_at: datetime


class DataQualityAlertPayload(BaseModel):
    """An automated quality check flagged a regression worth waking someone for."""

    model_config = _payload_config

    check_name: str = Field(description="Stable id of the check (e.g. 'odds_coverage_7d').")
    severity: Literal["info", "warning", "critical"]
    message: str
    affected_count: int = Field(default=0, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)

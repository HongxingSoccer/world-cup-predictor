"""Match-related DTOs returned by data-source adapters."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class MatchDTO(BaseModel):
    """A single match as observed from an external data source.

    The DTO is producer-agnostic: an API-Football response and a Transfermarkt
    scrape both materialize as `MatchDTO` instances, which the match pipeline
    then resolves to canonical entities and persists.
    """

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    external_id: str = Field(description="Source-native match id (e.g. API-Football fixture id).")
    home_team_name: str = Field(min_length=1, description="Raw home-team name from the source.")
    away_team_name: str = Field(min_length=1, description="Raw away-team name from the source.")
    match_date: datetime = Field(description="Kickoff datetime, normalized to UTC at validation.")
    status: str = Field(description="Source-mapped status: scheduled / live / finished / postponed / cancelled.")
    home_score: Optional[int] = Field(default=None, ge=0, description="Final or current home goals.")
    away_score: Optional[int] = Field(default=None, ge=0, description="Final or current away goals.")
    venue: Optional[str] = Field(default=None, description="Stadium name, if known.")
    round: Optional[str] = Field(default=None, description="Round / matchweek label (e.g. 'Group A', 'R16').")
    competition_name: str = Field(min_length=1, description="Competition name as reported by the source.")
    season_year: int = Field(
        ge=1872,
        le=2100,
        description=(
            "Season's starting year (e.g. 2026 for 2026 World Cup). "
            "Floor is 1872 — the year of the first international match (Scotland vs England)."
        ),
    )

    @model_validator(mode="after")
    def _coerce_match_date_to_utc(self) -> "MatchDTO":
        # Pydantic accepts naive datetimes; we treat them as already-UTC rather
        # than guessing local time. Aware datetimes are converted to UTC.
        if self.match_date.tzinfo is None:
            object.__setattr__(self, "match_date", self.match_date.replace(tzinfo=timezone.utc))
        else:
            object.__setattr__(self, "match_date", self.match_date.astimezone(timezone.utc))
        return self

    @model_validator(mode="after")
    def _check_score_consistency(self) -> "MatchDTO":
        # If one score is set the other must be too — half-populated rows are
        # almost always a parsing bug.
        if (self.home_score is None) != (self.away_score is None):
            raise ValueError("home_score and away_score must both be set or both be None")
        return self

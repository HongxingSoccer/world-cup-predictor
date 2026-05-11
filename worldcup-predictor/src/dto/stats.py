"""Match-stats and team-aggregate DTOs."""
from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from src.dto.match import MatchDTO
from src.dto.odds import OddsDTO
from src.dto.player import PlayerStatDTO


class MatchStatsDTO(BaseModel):
    """One team's aggregate stat line for one match.

    Two of these (home + away) materialize a row each in `match_stats`.
    """

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    match_external_id: str
    team_external_id: str
    is_home: bool

    possession: Decimal | None = Field(default=None, ge=0, le=100, description="Ball-possession percentage 0–100.")
    shots: int | None = Field(default=None, ge=0)
    shots_on_target: int | None = Field(default=None, ge=0)
    xg: Decimal | None = Field(default=None, ge=0, le=10)
    xg_against: Decimal | None = Field(default=None, ge=0, le=10)
    passes: int | None = Field(default=None, ge=0)
    pass_accuracy: Decimal | None = Field(default=None, ge=0, le=100)
    corners: int | None = Field(default=None, ge=0)
    fouls: int | None = Field(default=None, ge=0)
    yellow_cards: int | None = Field(default=None, ge=0)
    red_cards: int | None = Field(default=None, ge=0)
    offsides: int | None = Field(default=None, ge=0)
    tackles: int | None = Field(default=None, ge=0)
    interceptions: int | None = Field(default=None, ge=0)
    saves: int | None = Field(default=None, ge=0)

    data_source: str = Field(description="Provider tag, e.g. 'api_football' / 'fbref' / 'understat'.")


class MatchDetailDTO(BaseModel):
    """Composite payload describing everything an adapter knows about one match.

    Returned from `BaseDataSourceAdapter.fetch_match_detail()`. Downstream
    pipelines fan it out into the individual model tables.
    """

    model_config = ConfigDict(frozen=True)

    match: MatchDTO = Field(description="Core fixture information.")
    home_stats: MatchStatsDTO | None = Field(
        default=None, description="Home-team aggregate stats; may be None for unfinished matches."
    )
    away_stats: MatchStatsDTO | None = Field(default=None, description="Away-team aggregate stats.")
    player_stats: list[PlayerStatDTO] = Field(
        default_factory=list, description="Per-player stats for both teams in this match."
    )
    odds: list[OddsDTO] = Field(
        default_factory=list,
        description="Snapshot of bookmaker odds captured for this match (if the source carries them).",
    )


class TeamStatsDTO(BaseModel):
    """Season-to-date aggregated stats for a single team in a single competition.

    Used by features such as form / xG-per-90 rather than for direct persistence.
    """

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    team_external_id: str
    season_external_id: str = Field(description="Source-native season id.")
    matches_played: int = Field(ge=0)
    wins: int = Field(ge=0)
    draws: int = Field(ge=0)
    losses: int = Field(ge=0)
    goals_for: int = Field(ge=0)
    goals_against: int = Field(ge=0)
    xg_for: Decimal | None = Field(default=None, ge=0)
    xg_against: Decimal | None = Field(default=None, ge=0)
    clean_sheets: int | None = Field(default=None, ge=0)
    data_source: str

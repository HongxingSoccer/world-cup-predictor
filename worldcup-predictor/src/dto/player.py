"""Player-related DTOs (master data, single-match stats, valuations, injuries)."""
from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

# --- Master data ---


class PlayerDTO(BaseModel):
    """Player master record as observed from a single source."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    external_id: str = Field(description="Source-native player id.")
    name: str = Field(min_length=1, description="Full name as reported by the source.")
    nationality: str | None = Field(default=None, description="ISO country name or 3-letter code.")
    date_of_birth: date | None = Field(default=None)
    position: str | None = Field(
        default=None,
        description="Generic position code: GK / DF / MF / FW (or finer-grained sub-position).",
    )
    current_team_external_id: str | None = Field(
        default=None,
        description="Source-native team id of the player's current club; resolved later.",
    )
    national_team_external_id: str | None = Field(
        default=None,
        description="Source-native team id of the player's national team, if known.",
    )
    market_value_eur: int | None = Field(
        default=None, ge=0, description="Latest known market value in whole EUR."
    )
    photo_url: str | None = Field(default=None)


# --- Single-match performance ---


class PlayerStatDTO(BaseModel):
    """One player's stat line in one match."""

    model_config = ConfigDict(frozen=True)

    match_external_id: str = Field(description="Source-native match id.")
    player_external_id: str = Field(description="Source-native player id.")
    team_external_id: str = Field(description="Source-native team id (the team the player played for).")

    goals: int = Field(default=0, ge=0)
    assists: int = Field(default=0, ge=0)
    xg: Decimal | None = Field(default=None, ge=0, le=10, description="Expected goals; FBref/Understat only.")
    xa: Decimal | None = Field(default=None, ge=0, le=10, description="Expected assists.")
    shots: int | None = Field(default=None, ge=0)
    key_passes: int | None = Field(default=None, ge=0)
    tackles: int | None = Field(default=None, ge=0)
    interceptions: int | None = Field(default=None, ge=0)
    saves: int | None = Field(default=None, ge=0)
    yellow_cards: int = Field(default=0, ge=0, le=2)
    red_cards: int = Field(default=0, ge=0, le=1)


# --- Injuries ---


class InjuryDTO(BaseModel):
    """A player injury / unavailability record."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    player_external_id: str
    team_external_id: str | None = None
    injury_type: str | None = Field(default=None, description="Free-form description, e.g. 'Hamstring'.")
    severity: str | None = Field(
        default=None, description="Source-mapped: minor / moderate / major / season-ending."
    )
    start_date: date
    expected_return: date | None = None
    actual_return: date | None = None
    is_active: bool = Field(default=True, description="True if the player is still unavailable.")

    @model_validator(mode="after")
    def _check_dates_ordered(self) -> InjuryDTO:
        if self.actual_return is not None and self.actual_return < self.start_date:
            raise ValueError("actual_return cannot be before start_date")
        if (
            self.expected_return is not None
            and self.expected_return < self.start_date
        ):
            raise ValueError("expected_return cannot be before start_date")
        return self


# --- Valuations ---


class ValuationDTO(BaseModel):
    """A single market-value snapshot for a player on a given date."""

    model_config = ConfigDict(frozen=True)

    player_external_id: str
    team_external_id: str | None = None
    value_date: date = Field(description="Date the source assigned to this valuation.")
    market_value_eur: int = Field(gt=0, description="Market value in whole EUR.")
    captured_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When our scraper recorded the value (defaults to now in UTC).",
    )

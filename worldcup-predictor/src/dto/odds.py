"""Bookmaker-odds DTOs.

Generic across market types: `outcomes` is a flat dict keyed by outcome name
(``"home"`` / ``"draw"`` / ``"away"`` / ``"over"`` / ``"under"`` / ``"yes"``
/ ``"no"``). The odds pipeline maps these into the appropriate columns on
`odds_snapshots`.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

# Outcome keys we know how to persist on `odds_snapshots`.
ALLOWED_OUTCOME_KEYS: frozenset[str] = frozenset(
    {"home", "draw", "away", "over", "under", "yes", "no"}
)


class OddsDTO(BaseModel):
    """A single bookmaker's quote for a single market on a single match."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    match_external_id: str = Field(description="Source-native match id; resolves to matches.id downstream.")
    bookmaker: str = Field(min_length=1, description="Bookmaker code, e.g. 'pinnacle', 'bet365'.")
    market_type: str = Field(
        min_length=1,
        description="Market identifier: '1x2' / 'over_under' / 'btts' / 'asian_handicap' / 'correct_score'.",
    )
    market_value: Optional[str] = Field(
        default=None,
        description="Market line/handicap/score, e.g. '2.5' for OU, '-1.5' for AH; None for 1x2/btts.",
    )
    outcomes: dict[str, float] = Field(
        description="Outcome name → decimal odds. Keys must be a subset of ALLOWED_OUTCOME_KEYS.",
    )
    snapshot_at: datetime = Field(description="When the bookmaker quoted these odds (UTC).")

    @model_validator(mode="after")
    def _coerce_snapshot_at_to_utc(self) -> "OddsDTO":
        if self.snapshot_at.tzinfo is None:
            object.__setattr__(self, "snapshot_at", self.snapshot_at.replace(tzinfo=timezone.utc))
        else:
            object.__setattr__(self, "snapshot_at", self.snapshot_at.astimezone(timezone.utc))
        return self

    @model_validator(mode="after")
    def _check_outcomes(self) -> "OddsDTO":
        if not self.outcomes:
            raise ValueError("outcomes must contain at least one outcome")

        unknown = set(self.outcomes) - ALLOWED_OUTCOME_KEYS
        if unknown:
            raise ValueError(f"outcomes contains unknown keys: {sorted(unknown)}")

        for key, odds in self.outcomes.items():
            # Light bound-check here; the full domain rules live in
            # src.utils.validators so they can be reused from the pipeline.
            # Upper bound matches odds_snapshots Numeric(6,3) column ceiling and
            # accommodates longshot markets (e.g. World Cup outright winners).
            if odds < 1.01 or odds > 999.999:
                raise ValueError(f"odds[{key}]={odds} outside [1.01, 999.999]")
        return self

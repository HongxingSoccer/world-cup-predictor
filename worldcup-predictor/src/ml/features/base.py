"""Abstract base class for feature calculators.

Every calculator follows the same contract:

    1. ``get_feature_names()`` — declarative list of column names produced.
    2. ``compute(match_id, cutoff_date)`` — return ``{name: value}`` for one match.
    3. ``compute_batch(items)`` — bulk variant; default loops over ``compute``.

The `cutoff_date` parameter is the project's data-leakage guard. Every SQL
query inside a calculator MUST filter on ``match_date < :cutoff_date`` (or the
date-typed equivalent for `elo_ratings.rated_at` / `player_valuations.value_date`).
Test fixtures in `tests/test_features_*` pin this invariant down per module.

A `MatchContext` helper resolves match → (home_team_id, away_team_id, season_id,
team_type) once and is shared across calculators by the `FeaturePipeline` so we
don't issue six identical lookups per match.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models.match import Match
from src.models.team import Team

FeatureDict = dict[str, Any]


@dataclass(frozen=True)
class MatchContext:
    """Pre-resolved attributes of a match used by every calculator.

    Attributes:
        match_id: Internal `matches.id`.
        home_team_id: FK to `teams.id`.
        away_team_id: FK to `teams.id`.
        season_id: FK to `seasons.id` (used by home/away features).
        cutoff_date: Datetime to compare against `matches.match_date`.
            Inclusive bound is `<` (strictly less than) so a match never sees
            its own row in the training data.
        home_team_type: 'national' / 'club' — used by recent-form filter.
        away_team_type: 'national' / 'club'.
    """

    match_id: int
    home_team_id: int
    away_team_id: int
    season_id: int
    cutoff_date: datetime
    home_team_type: str
    away_team_type: str


class BaseFeatureCalculator(ABC):
    """Abstract calculator. Subclasses implement one feature group each."""

    def __init__(self, session: Session) -> None:
        self._session = session

    @abstractmethod
    def get_feature_names(self) -> list[str]:
        """List of feature names this calculator produces (stable order)."""

    @abstractmethod
    def compute(self, match_id: int, cutoff_date: datetime) -> FeatureDict:
        """Return ``{name: value}`` for one match. NaN-safe — never raises on missing data."""

    def compute_batch(
        self, items: Sequence[tuple[int, datetime]]
    ) -> list[FeatureDict]:
        """Default loop. Override only when batching beats N round-trips."""
        return [self.compute(match_id, cutoff) for match_id, cutoff in items]

    # --- Helper available to subclasses ---

    def _resolve_context(self, match_id: int, cutoff_date: datetime) -> MatchContext:
        """Single-query helper: match + home/away team_type."""
        stmt = (
            select(
                Match.id,
                Match.home_team_id,
                Match.away_team_id,
                Match.season_id,
                Team.team_type.label("home_team_type"),
            )
            .join(Team, Team.id == Match.home_team_id)
            .where(Match.id == match_id)
        )
        row = self._session.execute(stmt).first()
        if row is None:
            raise ValueError(f"Match {match_id} not found")

        away_type_stmt = (
            select(Team.team_type).where(Team.id == row.away_team_id)
        )
        away_type = self._session.execute(away_type_stmt).scalar_one()

        return MatchContext(
            match_id=row.id,
            home_team_id=row.home_team_id,
            away_team_id=row.away_team_id,
            season_id=row.season_id,
            cutoff_date=cutoff_date,
            home_team_type=row.home_team_type,
            away_team_type=away_type,
        )

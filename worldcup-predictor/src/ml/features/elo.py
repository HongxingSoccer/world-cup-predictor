"""Elo-rating features (4 columns).

We use the latest `elo_ratings` row per team where `rated_at < cutoff_date.date()`.
Falls back to 1500 (the project's seed rating) when a team has no history yet,
so brand-new entries return a neutral value rather than NaN.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import desc, select

from src.ml.features.base import BaseFeatureCalculator, FeatureDict
from src.models.elo_rating import EloRating
from src.utils.elo import INITIAL_RATING, expected_score

FEATURE_NAMES: list[str] = ["home_elo", "away_elo", "elo_diff", "elo_win_prob"]


class EloFeatures(BaseFeatureCalculator):
    """Compute Elo home/away/diff/win-prob from `elo_ratings`."""

    def get_feature_names(self) -> list[str]:
        return list(FEATURE_NAMES)

    def compute(self, match_id: int, cutoff_date: datetime) -> FeatureDict:
        ctx = self._resolve_context(match_id, cutoff_date)
        home_elo = self._latest_rating(ctx.home_team_id, cutoff_date)
        away_elo = self._latest_rating(ctx.away_team_id, cutoff_date)
        diff = home_elo - away_elo
        return {
            "home_elo": home_elo,
            "away_elo": away_elo,
            "elo_diff": diff,
            "elo_win_prob": expected_score(home_elo, away_elo),
        }

    def _latest_rating(self, team_id: int, cutoff_date: datetime) -> float:
        cutoff_d = cutoff_date.date()
        stmt = (
            select(EloRating.rating)
            .where(EloRating.team_id == team_id, EloRating.rated_at < cutoff_d)
            .order_by(desc(EloRating.rated_at), desc(EloRating.id))
            .limit(1)
        )
        result = self._session.execute(stmt).scalar()
        if result is None:
            return INITIAL_RATING
        # Both branches went through `float(...)` previously — the
        # `isinstance(Decimal)` check was vestigial.
        return float(result)

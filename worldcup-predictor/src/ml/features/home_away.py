"""Home/Away features (4 columns).

Within the *current season only* (matches sharing `season_id` with the target
match) and strictly before `cutoff_date`, compute:

    * home team's home-game win rate
    * away team's away-game win rate
    * home team's home-game scoring rate
    * away team's away-game scoring rate

These features capture venue effects (home advantage / road weakness) that
the season-agnostic recent-form features can dilute.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select

from src.ml.features.base import BaseFeatureCalculator, FeatureDict
from src.models.match import Match

FEATURE_NAMES: list[str] = [
    "home_home_win_rate",
    "away_away_win_rate",
    "home_home_goals_avg",
    "away_away_goals_avg",
]


class HomeAwayFeatures(BaseFeatureCalculator):
    """Compute season-scoped home / away splits for both teams."""

    def get_feature_names(self) -> list[str]:
        return list(FEATURE_NAMES)

    def compute(self, match_id: int, cutoff_date: datetime) -> FeatureDict:
        ctx = self._resolve_context(match_id, cutoff_date)
        home_at_home = self._home_split(ctx.home_team_id, ctx.season_id, cutoff_date)
        away_on_road = self._away_split(ctx.away_team_id, ctx.season_id, cutoff_date)
        return {
            "home_home_win_rate": home_at_home["win_rate"],
            "away_away_win_rate": away_on_road["win_rate"],
            "home_home_goals_avg": home_at_home["goals_avg"],
            "away_away_goals_avg": away_on_road["goals_avg"],
        }

    def _home_split(
        self, team_id: int, season_id: int, cutoff_date: datetime
    ) -> dict[str, float]:
        rows = self._fetch_split(
            team_id, season_id, cutoff_date, is_home=True
        )
        if not rows:
            return {"win_rate": 0.0, "goals_avg": 0.0}
        wins = sum(1 for r in rows if r.home_score > r.away_score)
        goals = sum(r.home_score for r in rows)
        return {"win_rate": wins / len(rows), "goals_avg": goals / len(rows)}

    def _away_split(
        self, team_id: int, season_id: int, cutoff_date: datetime
    ) -> dict[str, float]:
        rows = self._fetch_split(
            team_id, season_id, cutoff_date, is_home=False
        )
        if not rows:
            return {"win_rate": 0.0, "goals_avg": 0.0}
        wins = sum(1 for r in rows if r.away_score > r.home_score)
        goals = sum(r.away_score for r in rows)
        return {"win_rate": wins / len(rows), "goals_avg": goals / len(rows)}

    def _fetch_split(
        self,
        team_id: int,
        season_id: int,
        cutoff_date: datetime,
        *,
        is_home: bool,
    ) -> list[Any]:
        venue_filter = (
            Match.home_team_id == team_id if is_home else Match.away_team_id == team_id
        )
        stmt = (
            select(Match.home_score, Match.away_score)
            .where(
                venue_filter,
                Match.season_id == season_id,
                Match.status == "finished",
                Match.match_date < cutoff_date,
                Match.home_score.is_not(None),
                Match.away_score.is_not(None),
            )
        )
        return list(self._session.execute(stmt).all())

"""Head-to-Head features (3 columns).

Despite the existence of the `h2h_records` aggregate table, we recompute on
the fly from `matches` here so the cutoff filter can guarantee no future
data leaks in. `h2h_records` is a "current snapshot" used by inference; for
training and back-testing we always go back to source.

    * h2h_home_win_rate  : fraction of past meetings the home team won
    * h2h_total_matches  : total past meetings, capped at 50 to bound the feature
    * h2h_avg_goals      : average total goals per past meeting
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import and_, case, func, or_, select

from src.ml.features.base import BaseFeatureCalculator, FeatureDict
from src.models.match import Match

H2H_TOTAL_CAP: int = 50

FEATURE_NAMES: list[str] = [
    "h2h_home_win_rate",
    "h2h_total_matches",
    "h2h_avg_goals",
]


class H2HFeatures(BaseFeatureCalculator):
    """Compute past-meeting aggregates for the (home, away) pair."""

    def get_feature_names(self) -> list[str]:
        return list(FEATURE_NAMES)

    def compute(self, match_id: int, cutoff_date: datetime) -> FeatureDict:
        ctx = self._resolve_context(match_id, cutoff_date)
        result = self._aggregate(
            home_team_id=ctx.home_team_id,
            away_team_id=ctx.away_team_id,
            cutoff_date=cutoff_date,
        )
        total = int(result["total"] or 0)
        if total == 0:
            return {
                "h2h_home_win_rate": 0.0,
                "h2h_total_matches": 0,
                "h2h_avg_goals": 0.0,
            }

        home_wins = int(result["home_wins"] or 0)
        total_goals = int(result["total_goals"] or 0)
        return {
            "h2h_home_win_rate": home_wins / total,
            "h2h_total_matches": min(total, H2H_TOTAL_CAP),
            "h2h_avg_goals": total_goals / total,
        }

    def _aggregate(
        self,
        *,
        home_team_id: int,
        away_team_id: int,
        cutoff_date: datetime,
    ) -> dict[str, int | None]:
        # `home_wins` counts the *current home team* winning regardless of which
        # venue the past meeting was played at. The CASE WHEN enumerates the
        # two scenarios (current home was home / current home was away).
        home_won_when_home = and_(
            Match.home_team_id == home_team_id,
            Match.home_score > Match.away_score,
        )
        home_won_when_away = and_(
            Match.away_team_id == home_team_id,
            Match.away_score > Match.home_score,
        )
        home_wins_expr = func.sum(
            case((or_(home_won_when_home, home_won_when_away), 1), else_=0)
        )

        stmt = select(
            func.count(Match.id).label("total"),
            home_wins_expr.label("home_wins"),
            func.sum(Match.home_score + Match.away_score).label("total_goals"),
        ).where(
            Match.status == "finished",
            Match.match_date < cutoff_date,
            Match.home_score.is_not(None),
            Match.away_score.is_not(None),
            or_(
                and_(Match.home_team_id == home_team_id, Match.away_team_id == away_team_id),
                and_(Match.home_team_id == away_team_id, Match.away_team_id == home_team_id),
            ),
        )
        row = self._session.execute(stmt).one()
        return {
            "total": row.total,
            "home_wins": row.home_wins,
            "total_goals": row.total_goals,
        }

"""Recent-form features (8 columns).

For each team we look at the most-recent finished matches strictly before the
cutoff and compute:

    * win_rate_last5
    * goals_scored_avg5
    * goals_conceded_avg5
    * unbeaten_streak (consecutive non-losses ending at cutoff, capped at 20)

National-team and club histories are kept separate via a `team_type` filter on
the opponent — for a national team, only national-team matches count and
vice versa. The `unbeaten_streak` upper cap keeps the feature scale bounded
so models don't over-weight historic dominance.
"""
from __future__ import annotations

from datetime import datetime
from typing import NamedTuple

from sqlalchemy import desc, or_, select
from sqlalchemy.orm import aliased

from src.ml.features.base import BaseFeatureCalculator, FeatureDict
from src.models.match import Match
from src.models.team import Team

UNBEATEN_STREAK_CAP: int = 20
RECENT_WINDOW: int = 5

FEATURE_NAMES: list[str] = [
    "home_win_rate_last5",
    "away_win_rate_last5",
    "home_goals_scored_avg5",
    "away_goals_scored_avg5",
    "home_goals_conceded_avg5",
    "away_goals_conceded_avg5",
    "home_unbeaten_streak",
    "away_unbeaten_streak",
]


class _MatchOutcome(NamedTuple):
    is_home: bool
    home_score: int
    away_score: int


class RecentFormFeatures(BaseFeatureCalculator):
    """Build recent-form features per team."""

    def get_feature_names(self) -> list[str]:
        return list(FEATURE_NAMES)

    def compute(self, match_id: int, cutoff_date: datetime) -> FeatureDict:
        ctx = self._resolve_context(match_id, cutoff_date)
        home = self._team_stats(ctx.home_team_id, ctx.home_team_type, cutoff_date)
        away = self._team_stats(ctx.away_team_id, ctx.away_team_type, cutoff_date)
        return {
            "home_win_rate_last5": home["win_rate"],
            "away_win_rate_last5": away["win_rate"],
            "home_goals_scored_avg5": home["goals_for_avg"],
            "away_goals_scored_avg5": away["goals_for_avg"],
            "home_goals_conceded_avg5": home["goals_against_avg"],
            "away_goals_conceded_avg5": away["goals_against_avg"],
            "home_unbeaten_streak": home["unbeaten_streak"],
            "away_unbeaten_streak": away["unbeaten_streak"],
        }

    def _team_stats(
        self,
        team_id: int,
        team_type: str,
        cutoff_date: datetime,
    ) -> dict[str, float]:
        """Aggregate last-5 metrics + unbeaten streak for one team."""
        history = self._fetch_history(team_id, team_type, cutoff_date)
        if not history:
            return {"win_rate": 0.0, "goals_for_avg": 0.0, "goals_against_avg": 0.0, "unbeaten_streak": 0}

        last_n = history[:RECENT_WINDOW]
        wins, gf, ga = 0, 0, 0
        for outcome in last_n:
            our_score = outcome.home_score if outcome.is_home else outcome.away_score
            their_score = outcome.away_score if outcome.is_home else outcome.home_score
            gf += our_score
            ga += their_score
            if our_score > their_score:
                wins += 1

        return {
            "win_rate": wins / len(last_n),
            "goals_for_avg": gf / len(last_n),
            "goals_against_avg": ga / len(last_n),
            "unbeaten_streak": _unbeaten_streak(history),
        }

    def _fetch_history(
        self,
        team_id: int,
        team_type: str,
        cutoff_date: datetime,
    ) -> list[_MatchOutcome]:
        # Fetch up to (cap+1) so the streak walk has enough rows even if all
        # of them are unbeaten. We need cap+1 to "see the loss that ends it".
        limit = max(UNBEATEN_STREAK_CAP, RECENT_WINDOW) + 1

        # Filter by opponent's team_type so national vs club history don't mix.
        opp = aliased(Team)
        stmt = (
            select(Match.home_team_id, Match.home_score, Match.away_score)
            .join(
                opp,
                opp.id == _opponent_id_expr(team_id),
            )
            .where(
                or_(Match.home_team_id == team_id, Match.away_team_id == team_id),
                Match.status == "finished",
                Match.match_date < cutoff_date,
                Match.home_score.is_not(None),
                Match.away_score.is_not(None),
                opp.team_type == team_type,
            )
            .order_by(desc(Match.match_date), desc(Match.id))
            .limit(limit)
        )
        rows = self._session.execute(stmt).all()
        return [
            _MatchOutcome(
                is_home=row.home_team_id == team_id,
                home_score=row.home_score,
                away_score=row.away_score,
            )
            for row in rows
        ]


def _opponent_id_expr(team_id: int):  # type: ignore[no-untyped-def]
    """SQL CASE expression that returns the opponent's team id."""
    from sqlalchemy import case

    return case((Match.home_team_id == team_id, Match.away_team_id), else_=Match.home_team_id)


def _unbeaten_streak(history: list[_MatchOutcome]) -> int:
    """Count consecutive non-losses (most-recent first), capped."""
    streak = 0
    for outcome in history:
        our_score = outcome.home_score if outcome.is_home else outcome.away_score
        their_score = outcome.away_score if outcome.is_home else outcome.home_score
        if our_score < their_score:
            break
        streak += 1
        if streak >= UNBEATEN_STREAK_CAP:
            break
    return streak

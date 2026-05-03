"""Attack/Defense features (6 columns).

Per-team rolling-5 averages of expected goals (xG), expected goals against,
and shot accuracy (shots_on_target / shots). xG falls back to actual goals
when the upstream provider didn't ship xG (e.g. competitions outside the big
leagues' window). The fallback keeps the feature non-NaN at the cost of
slightly noisier signal — better than dropping the row.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import desc, select

from src.ml.features.base import BaseFeatureCalculator, FeatureDict
from src.models.match import Match
from src.models.match_stats import MatchStats

RECENT_WINDOW: int = 5

FEATURE_NAMES: list[str] = [
    "home_xg_avg5",
    "away_xg_avg5",
    "home_xg_against_avg5",
    "away_xg_against_avg5",
    "home_shot_accuracy_avg5",
    "away_shot_accuracy_avg5",
]


class AttackDefenseFeatures(BaseFeatureCalculator):
    """Compute rolling xG, xG-against, and shot accuracy per team."""

    def get_feature_names(self) -> list[str]:
        return list(FEATURE_NAMES)

    def compute(self, match_id: int, cutoff_date: datetime) -> FeatureDict:
        ctx = self._resolve_context(match_id, cutoff_date)
        home = self._team_metrics(ctx.home_team_id, cutoff_date)
        away = self._team_metrics(ctx.away_team_id, cutoff_date)
        return {
            "home_xg_avg5": home["xg"],
            "away_xg_avg5": away["xg"],
            "home_xg_against_avg5": home["xg_against"],
            "away_xg_against_avg5": away["xg_against"],
            "home_shot_accuracy_avg5": home["accuracy"],
            "away_shot_accuracy_avg5": away["accuracy"],
        }

    def _team_metrics(self, team_id: int, cutoff_date: datetime) -> dict[str, float]:
        """Average xG / xG-against / shot-accuracy across the last 5 matches."""
        rows = self._fetch_recent_stats(team_id, cutoff_date)
        if not rows:
            return {"xg": 0.0, "xg_against": 0.0, "accuracy": 0.0}

        xgs = [_xg_with_fallback(row, team_id) for row in rows]
        xg_agst = [
            float(row.xg_against) if row.xg_against is not None else float(_actual_against(row, team_id))
            for row in rows
        ]
        accuracies = [_accuracy(row.shots, row.shots_on_target) for row in rows]
        accuracies = [a for a in accuracies if a is not None]

        return {
            "xg": sum(xgs) / len(xgs),
            "xg_against": sum(xg_agst) / len(xg_agst),
            "accuracy": sum(accuracies) / len(accuracies) if accuracies else 0.0,
        }

    def _fetch_recent_stats(self, team_id: int, cutoff_date: datetime) -> list[Any]:
        stmt = (
            select(
                MatchStats.xg,
                MatchStats.xg_against,
                MatchStats.shots,
                MatchStats.shots_on_target,
                Match.home_team_id,
                Match.away_team_id,
                Match.home_score,
                Match.away_score,
            )
            .join(Match, Match.id == MatchStats.match_id)
            .where(
                MatchStats.team_id == team_id,
                Match.status == "finished",
                Match.match_date < cutoff_date,
            )
            .order_by(desc(Match.match_date), desc(Match.id))
            .limit(RECENT_WINDOW)
        )
        return list(self._session.execute(stmt).all())


def _xg_with_fallback(row: Any, team_id: int) -> float:
    """Use match_stats.xg; fall back to actual goals scored by the team."""
    if row.xg is not None:
        return float(row.xg)
    if row.home_team_id == team_id:
        return float(row.home_score or 0)
    return float(row.away_score or 0)


def _actual_against(row: Any, team_id: int) -> int:
    if row.home_team_id == team_id:
        return row.away_score or 0
    return row.home_score or 0


def _accuracy(shots: int | None, on_target: int | None) -> float | None:
    if not shots or shots == 0:
        return None
    if on_target is None:
        return None
    return on_target / shots

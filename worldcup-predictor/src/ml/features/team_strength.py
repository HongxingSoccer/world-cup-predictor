"""Team-strength features (3 columns).

Squad market-value as a proxy for talent depth. We sum the latest valuation
strictly before `cutoff_date` for every player with `current_team_id == team`.

Caveats (acknowledged Phase-2 simplification):
    * `players.current_team_id` is the *latest* roster, not a roster snapshot
      from `cutoff_date`. Phase 3 introduces a `team_rosters` history table to
      remove this leakage source. For Phase 2 the proxy is good enough — most
      "national team for this World Cup cycle" rosters don't change much.
    * We log10(value + 1) so a missing-data team (sum=0) yields 0 rather than
      -inf.
"""
from __future__ import annotations

import math
from datetime import datetime
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.orm import aliased

from src.ml.features.base import BaseFeatureCalculator, FeatureDict
from src.models.player import Player
from src.models.player_valuation import PlayerValuation

FEATURE_NAMES: list[str] = [
    "home_squad_value_log",
    "away_squad_value_log",
    "value_ratio",
]


class TeamStrengthFeatures(BaseFeatureCalculator):
    """Sum-of-latest-valuations proxy for squad strength."""

    def get_feature_names(self) -> list[str]:
        return list(FEATURE_NAMES)

    def compute(self, match_id: int, cutoff_date: datetime) -> FeatureDict:
        ctx = self._resolve_context(match_id, cutoff_date)
        home_value = self._squad_value(ctx.home_team_id, cutoff_date)
        away_value = self._squad_value(ctx.away_team_id, cutoff_date)
        return {
            "home_squad_value_log": math.log10(home_value + 1.0),
            "away_squad_value_log": math.log10(away_value + 1.0),
            "value_ratio": _safe_log_ratio(home_value, away_value),
        }

    def _squad_value(self, team_id: int, cutoff_date: datetime) -> float:
        """Sum the latest pre-cutoff valuation for each current squad member."""
        cutoff_d = cutoff_date.date()

        # Subquery: latest pre-cutoff value_date per (player_id).
        latest = (
            select(
                PlayerValuation.player_id.label("player_id"),
                func.max(PlayerValuation.value_date).label("latest_date"),
            )
            .where(PlayerValuation.value_date < cutoff_d)
            .group_by(PlayerValuation.player_id)
            .subquery("latest_valuations")
        )
        pv: Any = aliased(PlayerValuation)
        stmt = (
            select(func.coalesce(func.sum(pv.market_value_eur), 0))
            .select_from(Player)
            .join(latest, latest.c.player_id == Player.id)
            .join(
                pv,
                and_(
                    pv.player_id == latest.c.player_id,
                    pv.value_date == latest.c.latest_date,
                ),
            )
            .where(Player.current_team_id == team_id)
        )
        return float(self._session.execute(stmt).scalar_one() or 0.0)


def _safe_log_ratio(home_value: float, away_value: float) -> float:
    """log(home/away) with both-zero / one-zero safeguards.

    Returns 0.0 when either side is zero (no signal) rather than ±inf, so the
    feature column stays well-behaved.
    """
    if home_value <= 0.0 or away_value <= 0.0:
        return 0.0
    return math.log(home_value / away_value)

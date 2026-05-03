"""Trivial baselines for backtest comparison.

All four implement `BasePredictionModel` so they slot into `BacktestRunner`
unchanged. Each returns a degenerate but coherent `PredictionResult`:

    * `RandomBaseline`        — uniform 1/3-1/3-1/3.
    * `HomeWinBaseline`       — always favours the home side.
    * `EloOnlyBaseline`       — derives 1x2 from `elo_win_prob` alone.
    * `OddsImpliedBaseline`   — uses the bookmaker's de-vigged 1x2 prices as
      the prediction (the strongest baseline most models struggle to beat).

These are *not* meant to ship to production — they exist purely as comparison
points in the backtest report.
"""
from __future__ import annotations

import random
from typing import Any

import pandas as pd

from src.ml.models.base import BasePredictionModel, PredictionResult
from src.ml.odds.vig_removal import remove_vig

# Score matrix is a 1×1 placeholder for baselines (we only care about 1x2).
_FILLER_MATRIX: list[list[float]] = [[0.0] * 10 for _ in range(10)]
_FILLER_OU: dict[str, dict[str, float]] = {
    "1.5": {"over": 0.5, "under": 0.5},
    "2.5": {"over": 0.5, "under": 0.5},
    "3.5": {"over": 0.5, "under": 0.5},
}


def _make_result(
    home: float, draw: float, away: float, *, lambda_home: float = 1.5, lambda_away: float = 1.0
) -> PredictionResult:
    return PredictionResult(
        prob_home_win=home,
        prob_draw=draw,
        prob_away_win=away,
        lambda_home=lambda_home,
        lambda_away=lambda_away,
        score_matrix=_FILLER_MATRIX,
        top_scores=[],
        over_under_probs=_FILLER_OU,
        btts_prob=0.5,
    )


# --- Concrete baselines -----------------------------------------------------


class RandomBaseline(BasePredictionModel):
    """Uniform 1/3 across home / draw / away. Sanity-check floor."""

    def __init__(self, *, seed: int = 42) -> None:
        super().__init__()
        self._rng = random.Random(seed)

    def get_model_version(self) -> str:
        return "baseline_random"

    def train(self, features_df: pd.DataFrame) -> None:
        self.params = {"n_train_rows": len(features_df)}

    def predict(self, features: dict[str, Any]) -> PredictionResult:
        return _make_result(1 / 3, 1 / 3, 1 / 3)


class HomeWinBaseline(BasePredictionModel):
    """Always predict the home side wins. Tests the home-advantage prior alone."""

    def get_model_version(self) -> str:
        return "baseline_home_win"

    def train(self, features_df: pd.DataFrame) -> None:
        # Calibrate the home-win probability to the empirical training rate.
        if features_df.empty:
            home_rate = 0.45
        else:
            home_rate = float(
                (features_df["label_home_score"] > features_df["label_away_score"]).mean()
            )
        self.params = {"home_win_rate": home_rate}

    def predict(self, features: dict[str, Any]) -> PredictionResult:
        home = self.params.get("home_win_rate", 0.45)
        draw = (1 - home) / 2
        return _make_result(home, draw, 1 - home - draw)


class EloOnlyBaseline(BasePredictionModel):
    """Use `elo_win_prob` for home, split the rest 50/50 between draw and away.

    Cheaper than fitting a logistic but enough to test whether the rest of
    the feature stack adds signal beyond Elo.
    """

    DRAW_FLOOR: float = 0.22  # historical baseline draw rate

    def get_model_version(self) -> str:
        return "baseline_elo_only"

    def train(self, features_df: pd.DataFrame) -> None:
        self.params = {"n_train_rows": len(features_df)}

    def predict(self, features: dict[str, Any]) -> PredictionResult:
        elo_win = float(features.get("elo_win_prob") or 0.5)
        draw = self.DRAW_FLOOR
        home = elo_win * (1 - draw)
        away = (1 - elo_win) * (1 - draw)
        return _make_result(home, draw, away)


class OddsImpliedBaseline(BasePredictionModel):
    """Treat de-vigged bookmaker odds as the prediction. The hardest baseline to beat.

    Expects the calling environment to attach a feature called ``odds_1x2``
    formatted as ``{"home": float, "draw": float, "away": float}``. When the
    feature is missing or invalid, falls back to a uniform prior.
    """

    def get_model_version(self) -> str:
        return "baseline_odds_implied"

    def train(self, features_df: pd.DataFrame) -> None:
        self.params = {"n_train_rows": len(features_df)}

    def predict(self, features: dict[str, Any]) -> PredictionResult:
        raw = features.get("odds_1x2") or {}
        try:
            fair = remove_vig(raw)
            return _make_result(
                home=float(fair.get("home", 1 / 3)),
                draw=float(fair.get("draw", 1 / 3)),
                away=float(fair.get("away", 1 / 3)),
            )
        except (ValueError, TypeError):
            return _make_result(1 / 3, 1 / 3, 1 / 3)

"""XGBoost multi-head match-prediction model (Phase 4 v2 — design-aligned).

Implements ``docs/design/06_Phase4_ModelEvolution.md §3.3``: instead of a
single 1x2 classifier, we train **five sub-models** that share the same
feature DataFrame and produce all the outputs the ensemble layer needs:

    * ``model_1x2``         — multi:softprob (home/draw/away)
    * ``model_goals_home``  — count:poisson  (λ_home)
    * ``model_goals_away``  — count:poisson  (λ_away)
    * ``model_ou25``        — binary:logistic (>2.5 goals)
    * ``model_btts``        — binary:logistic (both teams to score)

The 1x2 classifier feeds the outcome marginal of the score matrix; the two
Poisson regressors give us λ values that build the matrix grid; OU 2.5 and
BTTS come straight from their dedicated heads (more accurate than reading
them off a Poisson grid, per design §3.4).
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import structlog
from scipy.stats import poisson

from src.ml.models.base import BasePredictionModel, PredictionResult
from src.ml.models.poisson import (
    OVER_UNDER_LINES,
    SCORE_MATRIX_SIZE,
    TOP_SCORES_K,
    _outcome_probs,
    _over_under_probs,
    _top_k_scores,
)

logger = structlog.get_logger(__name__)

MODEL_VERSION: str = "xgboost_v2"
DEFAULT_FEATURES: tuple[str, ...] = (
    "home_xg_avg5",
    "away_xg_avg5",
    "home_goals_scored_avg5",
    "away_goals_scored_avg5",
    "home_xg_against_avg5",
    "away_xg_against_avg5",
    "home_goals_conceded_avg5",
    "away_goals_conceded_avg5",
    "elo_diff",
    "h2h_home_win_rate",
    "home_form_points",
    "away_form_points",
)
OUTCOME_HOME: int = 0
OUTCOME_DRAW: int = 1
OUTCOME_AWAY: int = 2
OU25_THRESHOLD: float = 2.5


class XGBoostMatchModel(BasePredictionModel):
    """Five gradient-boosted heads packaged behind one :class:`PredictionResult`."""

    def __init__(
        self,
        *,
        feature_columns: tuple[str, ...] = DEFAULT_FEATURES,
        n_estimators: int = 200,
        max_depth: int = 4,
        learning_rate: float = 0.05,
    ) -> None:
        super().__init__()
        self._feature_columns = feature_columns
        self._n_estimators = n_estimators
        self._max_depth = max_depth
        self._learning_rate = learning_rate

        self._clf_1x2: Any | None = None
        self._reg_goals_home: Any | None = None
        self._reg_goals_away: Any | None = None
        self._clf_ou25: Any | None = None
        self._clf_btts: Any | None = None

    def get_model_version(self) -> str:
        return MODEL_VERSION

    # --- Training ---------------------------------------------------------

    def train(self, features_df: pd.DataFrame) -> None:
        """Fit all 5 sub-models from the same labelled DataFrame."""
        labels = features_df.dropna(subset=["label_home_score", "label_away_score"])
        if labels.empty:
            raise ValueError("training set has no rows with both labels populated")

        x = self._extract_features(labels)
        y_1x2 = _encode_outcome(labels["label_home_score"], labels["label_away_score"])
        y_goals_home = labels["label_home_score"].astype(float).to_numpy()
        y_goals_away = labels["label_away_score"].astype(float).to_numpy()
        total_goals = y_goals_home + y_goals_away
        y_ou25 = (total_goals > OU25_THRESHOLD).astype(int)
        y_btts = ((y_goals_home > 0) & (y_goals_away > 0)).astype(int)

        common = dict(
            n_estimators=self._n_estimators,
            max_depth=self._max_depth,
            learning_rate=self._learning_rate,
        )
        self._clf_1x2 = _train_softprob(x, y_1x2, **common)
        self._reg_goals_home = _train_poisson(x, y_goals_home, **common)
        self._reg_goals_away = _train_poisson(x, y_goals_away, **common)
        self._clf_ou25 = _train_binary(x, y_ou25, **common)
        self._clf_btts = _train_binary(x, y_btts, **common)

        league_avg_goals = float(total_goals.mean() / 2.0)
        self.params = {
            "league_avg_goals": league_avg_goals,
            "feature_columns": list(self._feature_columns),
            "trained_on_n_matches": len(labels),
            "n_estimators": self._n_estimators,
            "sub_models": [
                "1x2",
                "goals_home",
                "goals_away",
                "ou25",
                "btts",
            ],
        }
        logger.info("xgboost_trained", **self.params)

    # --- Inference --------------------------------------------------------

    def predict(self, features: dict[str, Any]) -> PredictionResult:
        if self._clf_1x2 is None:
            raise RuntimeError("model is untrained — call .train() first")
        row = np.array(
            [[float(features.get(col) or 0.0) for col in self._feature_columns]],
            dtype=float,
        )
        outcome_probs = self._clf_1x2.predict_proba(row)[0]
        prob_home = float(outcome_probs[OUTCOME_HOME])
        prob_draw = float(outcome_probs[OUTCOME_DRAW])
        prob_away = float(outcome_probs[OUTCOME_AWAY])
        lambda_home = float(self._reg_goals_home.predict(row)[0])
        lambda_away = float(self._reg_goals_away.predict(row)[0])
        prob_ou25_over = float(self._clf_ou25.predict_proba(row)[0][1])
        prob_btts = float(self._clf_btts.predict_proba(row)[0][1])

        matrix = _poisson_grid(lambda_home, lambda_away, size=SCORE_MATRIX_SIZE)
        matrix = _rescale_to_match_outcomes(matrix, prob_home, prob_draw, prob_away)

        # Override OU / BTTS with the dedicated heads (design §3.4).
        ou_probs = dict(_over_under_probs(matrix, lines=OVER_UNDER_LINES))
        ou_probs[OU25_THRESHOLD] = prob_ou25_over

        return PredictionResult(
            prob_home_win=prob_home,
            prob_draw=prob_draw,
            prob_away_win=prob_away,
            lambda_home=lambda_home,
            lambda_away=lambda_away,
            score_matrix=matrix,
            top_scores=_top_k_scores(matrix, k=TOP_SCORES_K),
            over_under_probs=ou_probs,
            btts_prob=prob_btts,
        )

    # --- Internal ---------------------------------------------------------

    def _extract_features(self, df: pd.DataFrame) -> np.ndarray:
        cols = [df.get(col) for col in self._feature_columns]
        arrays = [
            pd.to_numeric(c, errors="coerce").fillna(0.0).to_numpy(dtype=float)
            if c is not None
            else np.zeros(len(df), dtype=float)
            for c in cols
        ]
        return np.column_stack(arrays)


# --- Helpers ----------------------------------------------------------------


def _encode_outcome(home_scores: pd.Series, away_scores: pd.Series) -> np.ndarray:
    """Encode (home, away) score → 0/1/2 for home_win/draw/away_win."""
    diff = home_scores.to_numpy() - away_scores.to_numpy()
    out = np.full(diff.shape, OUTCOME_DRAW, dtype=int)
    out[diff > 0] = OUTCOME_HOME
    out[diff < 0] = OUTCOME_AWAY
    return out


def _xgb():
    import xgboost as xgb

    return xgb


def _train_softprob(
    x: np.ndarray, y: np.ndarray, *, n_estimators: int, max_depth: int, learning_rate: float
) -> Any:
    booster = _xgb().XGBClassifier(
        objective="multi:softprob",
        num_class=3,
        n_estimators=n_estimators,
        max_depth=max_depth,
        learning_rate=learning_rate,
        eval_metric="mlogloss",
        tree_method="hist",
        verbosity=0,
    )
    booster.fit(x, y)
    return booster


def _train_poisson(
    x: np.ndarray, y: np.ndarray, *, n_estimators: int, max_depth: int, learning_rate: float
) -> Any:
    booster = _xgb().XGBRegressor(
        objective="count:poisson",
        n_estimators=n_estimators,
        max_depth=max_depth,
        learning_rate=learning_rate,
        eval_metric="poisson-nloglik",
        tree_method="hist",
        verbosity=0,
    )
    booster.fit(x, y)
    return booster


def _train_binary(
    x: np.ndarray, y: np.ndarray, *, n_estimators: int, max_depth: int, learning_rate: float
) -> Any:
    booster = _xgb().XGBClassifier(
        objective="binary:logistic",
        n_estimators=n_estimators,
        max_depth=max_depth,
        learning_rate=learning_rate,
        eval_metric="logloss",
        tree_method="hist",
        verbosity=0,
    )
    booster.fit(x, y)
    return booster


def _poisson_grid(lambda_home: float, lambda_away: float, *, size: int) -> list[list[float]]:
    indices = np.arange(size)
    matrix = np.outer(poisson.pmf(indices, lambda_home), poisson.pmf(indices, lambda_away))
    total = float(matrix.sum())
    if total > 0:
        matrix = matrix / total
    return matrix.tolist()


def _rescale_to_match_outcomes(
    matrix: list[list[float]], prob_home: float, prob_draw: float, prob_away: float
) -> list[list[float]]:
    """Reweight rows so the marginal 1x2 distribution matches the classifier."""
    arr = np.asarray(matrix)
    cur_home, cur_draw, cur_away = _outcome_probs(matrix)
    n = arr.shape[0]
    i, j = np.indices((n, n))
    factors = np.ones_like(arr)
    factors[i > j] = prob_home / cur_home if cur_home > 0 else 1.0
    factors[i == j] = prob_draw / cur_draw if cur_draw > 0 else 1.0
    factors[i < j] = prob_away / cur_away if cur_away > 0 else 1.0
    arr = arr * factors
    total = float(arr.sum())
    return (arr / total if total > 0 else arr).tolist()

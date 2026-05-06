"""Poisson regression goal model — log-linear λ from Elo + xG + form features.

The Phase-2 :class:`PoissonBaselineModel` derives λ multiplicatively from
rolling windows and applies a small Elo nudge as a post-hoc multiplier.
On our backtest the Elo-only baseline beats it by ~7 percentage points,
which suggests Elo carries strong signal that the multiplicative
formulation is throwing away.

This model follows the Groll / Hvattum & Arntzen pattern: fit a single
Poisson GLM with log link by maximum likelihood,

    log λ = β₀ + β₁·elo_diff + β₂·xg_for + β₃·xg_against + … + h·is_home

with one observation per (match, scoring side). Coefficients are shared
across home / away rows and the home advantage is captured by an
``is_home`` indicator. Inference replays the same coefficients on a feature
vector built per side; the joint score matrix is reused from the
independent-Poisson helpers in :mod:`src.ml.models.poisson`.

References (see also `docs/research/elo_blending.md`):

- Hvattum & Arntzen (2010), "Using ELO ratings for match result prediction
  in association football."
- Groll, Schauberger, Tutz et al. (2018+), hybrid random-forest + Poisson
  team-ability ratings on World Cup / Euro data.
- Wunderlich & Memmert (2018), "Are betting returns a useful measure of
  accuracy in (sports) forecasting?" — odds-inversion baseline.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import structlog
from sklearn.linear_model import PoissonRegressor
from sklearn.preprocessing import StandardScaler

from src.ml.models.base import BasePredictionModel, PredictionResult
from src.ml.models.poisson import (
    OVER_UNDER_LINES,
    SCORE_MATRIX_SIZE,
    TOP_SCORES_K,
    _btts_yes_prob,
    _outcome_probs,
    _over_under_probs,
    _score_matrix,
    _top_k_scores,
)

logger = structlog.get_logger(__name__)

MODEL_VERSION: str = "poisson_glm_v1"

# Feature names in stable order — same vector for both home and away
# observations during training, with the side flipped (elo sign, xG-for /
# xG-against, etc.). is_home is the only home-advantage encoding.
FEATURE_NAMES: tuple[str, ...] = (
    "elo_diff_signed",
    "team_xg_for",
    "team_xg_against",
    "team_goals_for",
    "team_goals_against",
    "team_form_win_rate",
    "team_recent_unbeaten",
    "is_home",
)

DEFAULT_REGULARISATION: float = 0.01  # sklearn's PoissonRegressor `alpha`


class PoissonGLMModel(BasePredictionModel):
    """Poisson GLM trained by sklearn's MLE solver."""

    def get_model_version(self) -> str:
        return MODEL_VERSION

    # --- Training ---------------------------------------------------------

    def train(self, features_df: pd.DataFrame) -> None:
        labels = features_df.dropna(subset=["label_home_score", "label_away_score"])
        if labels.empty:
            raise ValueError("training set has no rows with both labels populated")

        long_df = self._to_long_format(labels)
        x_train_raw = long_df[list(FEATURE_NAMES)].to_numpy(dtype=float)
        y_train = long_df["goals"].to_numpy(dtype=float)

        # Standardise before fitting. Without this, ``elo_diff`` (std ≈ 250)
        # gets penalised hundreds of times harder than xG (std ≈ 0.3) under
        # the L2 prior, and the optimiser collapses every coefficient to 0.
        # ``is_home`` would also lose all its mass; with scaling it survives.
        scaler = StandardScaler()
        x_train = scaler.fit_transform(x_train_raw)

        regressor = PoissonRegressor(
            alpha=DEFAULT_REGULARISATION, max_iter=500, tol=1e-7
        )
        regressor.fit(x_train, y_train)
        self._regressor = regressor
        self._scaler = scaler

        self.params = {
            "intercept": float(regressor.intercept_),
            "coef": [float(c) for c in regressor.coef_],
            "feature_names": list(FEATURE_NAMES),
            "scaler_mean": [float(m) for m in scaler.mean_],
            "scaler_scale": [float(s) for s in scaler.scale_],
            "regularisation_alpha": DEFAULT_REGULARISATION,
            "trained_on_n_matches": int(len(labels)),
        }
        coef_repr = {
            name: round(float(c), 4)
            for name, c in zip(FEATURE_NAMES, regressor.coef_)
        }
        logger.info(
            "poisson_glm_trained",
            intercept=round(float(regressor.intercept_), 4),
            standardised_coefficients=coef_repr,
            n_long_rows=len(long_df),
            n_matches=len(labels),
        )

    # --- Inference --------------------------------------------------------

    def predict(self, features: dict[str, Any]) -> PredictionResult:
        if not self.params:
            raise RuntimeError("model is untrained — call .train() first")

        # Compute λ = exp(intercept + coef · standardised(x)) by hand.
        # Going through `regressor.predict()` would require restoring sklearn's
        # internal `_base_loss` attribute (only set during `.fit`), and our
        # JSON save/load round-trip doesn't carry it. The math here is
        # equivalent to PoissonRegressor.predict for a fitted log-link model.
        coef = np.asarray(self.params["coef"], dtype=float)
        intercept = float(self.params["intercept"])
        scaler_mean = np.asarray(self.params["scaler_mean"], dtype=float)
        scaler_scale = np.asarray(self.params["scaler_scale"], dtype=float)
        x_home = np.asarray(self._row_features(features, perspective="home"))
        x_away = np.asarray(self._row_features(features, perspective="away"))
        x_home_scaled = (x_home - scaler_mean) / scaler_scale
        x_away_scaled = (x_away - scaler_mean) / scaler_scale
        lambda_home = float(np.exp(intercept + coef @ x_home_scaled))
        lambda_away = float(np.exp(intercept + coef @ x_away_scaled))

        # Defend against extreme inputs that exploded the linear predictor.
        lambda_home = float(np.clip(lambda_home, 0.05, 8.0))
        lambda_away = float(np.clip(lambda_away, 0.05, 8.0))

        score_matrix = _score_matrix(lambda_home, lambda_away, size=SCORE_MATRIX_SIZE)
        prob_h, prob_d, prob_a = _outcome_probs(score_matrix)
        return PredictionResult(
            prob_home_win=prob_h,
            prob_draw=prob_d,
            prob_away_win=prob_a,
            lambda_home=lambda_home,
            lambda_away=lambda_away,
            score_matrix=score_matrix,
            top_scores=_top_k_scores(score_matrix, k=TOP_SCORES_K),
            over_under_probs=_over_under_probs(score_matrix, lines=OVER_UNDER_LINES),
            btts_prob=_btts_yes_prob(score_matrix),
        )

    # --- Feature plumbing -------------------------------------------------

    @staticmethod
    def _to_long_format(labels: pd.DataFrame) -> pd.DataFrame:
        """Two rows per match: one with the home side scoring, one away.

        Coefficients are shared, so the two rows let one Poisson fit learn a
        single set of weights on the side-symmetric features (elo_diff
        flips sign, xG-for and xG-against swap home↔away, etc.). The
        ``is_home`` indicator captures home advantage as a single intercept
        shift instead of needing a separate model per side."""
        rows: list[dict[str, float]] = []
        for _, row in labels.iterrows():
            elo_diff = _safe_float(row.get("elo_diff"), default=0.0)
            home_unbeaten = _safe_float(row.get("home_unbeaten_streak"), default=0.0)
            away_unbeaten = _safe_float(row.get("away_unbeaten_streak"), default=0.0)
            home_form = _safe_float(row.get("home_win_rate_last5"), default=0.0)
            away_form = _safe_float(row.get("away_win_rate_last5"), default=0.0)

            rows.append({
                "elo_diff_signed": elo_diff,
                "team_xg_for": _safe_float(row.get("home_xg_avg5"), default=0.0),
                "team_xg_against": _safe_float(row.get("home_xg_against_avg5"), default=0.0),
                "team_goals_for": _safe_float(row.get("home_goals_scored_avg5"), default=0.0),
                "team_goals_against": _safe_float(row.get("home_goals_conceded_avg5"), default=0.0),
                "team_form_win_rate": home_form,
                "team_recent_unbeaten": home_unbeaten,
                "is_home": 1.0,
                "goals": float(row["label_home_score"]),
            })
            rows.append({
                "elo_diff_signed": -elo_diff,
                "team_xg_for": _safe_float(row.get("away_xg_avg5"), default=0.0),
                "team_xg_against": _safe_float(row.get("away_xg_against_avg5"), default=0.0),
                "team_goals_for": _safe_float(row.get("away_goals_scored_avg5"), default=0.0),
                "team_goals_against": _safe_float(row.get("away_goals_conceded_avg5"), default=0.0),
                "team_form_win_rate": away_form,
                "team_recent_unbeaten": away_unbeaten,
                "is_home": 0.0,
                "goals": float(row["label_away_score"]),
            })
        return pd.DataFrame.from_records(rows)

    @staticmethod
    def _row_features(features: dict[str, Any], *, perspective: str) -> list[float]:
        """Build the 8-element feature vector for one perspective at predict time."""
        elo_diff = _safe_float(features.get("elo_diff"), default=0.0)
        if perspective == "home":
            return [
                elo_diff,
                _safe_float(features.get("home_xg_avg5"), default=0.0),
                _safe_float(features.get("home_xg_against_avg5"), default=0.0),
                _safe_float(features.get("home_goals_scored_avg5"), default=0.0),
                _safe_float(features.get("home_goals_conceded_avg5"), default=0.0),
                _safe_float(features.get("home_win_rate_last5"), default=0.0),
                _safe_float(features.get("home_unbeaten_streak"), default=0.0),
                1.0,
            ]
        return [
            -elo_diff,
            _safe_float(features.get("away_xg_avg5"), default=0.0),
            _safe_float(features.get("away_xg_against_avg5"), default=0.0),
            _safe_float(features.get("away_goals_scored_avg5"), default=0.0),
            _safe_float(features.get("away_goals_conceded_avg5"), default=0.0),
            _safe_float(features.get("away_win_rate_last5"), default=0.0),
            _safe_float(features.get("away_unbeaten_streak"), default=0.0),
            0.0,
        ]

    # No _reload_regressor / _reload_scaler: predict() now does the
    # log-link math directly from coef/intercept/scaler_mean/scaler_scale,
    # which all round-trip through JSON cleanly.


# --- Module helpers ---------------------------------------------------------


def _safe_float(value: Any, *, default: float) -> float:
    """Coerce maybe-None / NaN / pd.NA to a safe float."""
    if value is None:
        return default
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    if not np.isfinite(out):
        return default
    return out

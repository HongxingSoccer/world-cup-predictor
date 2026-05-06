"""Poisson baseline match-prediction model (Phase 2 v1).

Computes expected goals λ for each side from per-team attack / defense
strengths and the league-average scoring rate, then derives match outcomes
from the standard independent-Poisson approximation:

    P(home=i, away=j) = poisson.pmf(i, λ_home) × poisson.pmf(j, λ_away)

`train()` fits four scalar parameters (`league_avg_goals`,
`league_avg_attack`, `league_avg_defense`, `home_factor`) from the supplied
feature DataFrame's labels. `predict()` is pure math and does no DB I/O.

Reference: Dixon & Coles (1997) — *Modelling Association Football Scores
and Inefficiencies in the Football Betting Market*. Phase 2 omits the time-
weighted likelihood and the low-score correlation correction; both arrive
in a later Poisson-v2 model.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import structlog
from scipy.stats import poisson

from src.ml.models.base import BasePredictionModel, PredictionResult

logger = structlog.get_logger(__name__)

# Compile-time constants ------------------------------------------------------

MODEL_VERSION: str = "poisson_v1"
DEFAULT_HOME_FACTOR: float = 1.2
XG_WEIGHT: float = 0.6  # 60% xG, 40% actual goals (per spec)
SCORE_MATRIX_SIZE: int = 10
OVER_UNDER_LINES: tuple[float, ...] = (1.5, 2.5, 3.5)
TOP_SCORES_K: int = 10
ELO_THRESHOLD: float = 200.0  # |elo_diff| > this triggers the ±5% adjustment
ELO_ADJ: float = 0.05


class PoissonBaselineModel(BasePredictionModel):
    """Independent-Poisson goal model with attack/defense scaling + Elo nudge."""

    def get_model_version(self) -> str:
        return MODEL_VERSION

    # --- Training ---------------------------------------------------------

    def train(self, features_df: pd.DataFrame) -> None:
        labels = features_df.dropna(subset=["label_home_score", "label_away_score"])
        if labels.empty:
            raise ValueError("training set has no rows with both labels populated")

        league_avg_goals = float(
            (labels["label_home_score"].mean() + labels["label_away_score"].mean()) / 2.0
        )

        atk_home = _row_attack(labels, side="home")
        atk_away = _row_attack(labels, side="away")
        def_home = _row_defense(labels, side="home")
        def_away = _row_defense(labels, side="away")

        # League averages across both sides combined — reflects the typical
        # scoring potential / leakiness, used to normalise per-row strengths.
        league_avg_attack = float(np.nanmean(np.concatenate([atk_home, atk_away])))
        league_avg_defense = float(np.nanmean(np.concatenate([def_home, def_away])))
        if league_avg_attack <= 0 or league_avg_defense <= 0:
            league_avg_attack = league_avg_attack or 1.0
            league_avg_defense = league_avg_defense or 1.0

        # Calibrate home factor by comparing actual home win rate to the
        # rate implied by attack/defense alone. Capped at [1.05, 1.40] to
        # keep extreme small-sample training sets from blowing this up.
        home_factor = self._calibrate_home_factor(labels)

        self.params = {
            "league_avg_goals": league_avg_goals,
            "league_avg_attack": league_avg_attack,
            "league_avg_defense": league_avg_defense,
            "home_factor": home_factor,
            "trained_on_n_matches": int(len(labels)),
        }
        logger.info("poisson_trained", **self.params)

    # --- Inference --------------------------------------------------------

    def predict(self, features: dict[str, Any]) -> PredictionResult:
        if not self.params:
            raise RuntimeError("model is untrained — call .train() first")

        atk_home = _attack_from_features(features, "home")
        atk_away = _attack_from_features(features, "away")
        def_home = _defense_from_features(features, "home")
        def_away = _defense_from_features(features, "away")

        league_g = self.params["league_avg_goals"]
        league_a = self.params["league_avg_attack"]
        league_d = self.params["league_avg_defense"]
        home_factor = self.params["home_factor"]

        # Fallback: zero attack/defense (no historical signal) reverts to the
        # league baseline so we never hand back λ=0 (which would lock the
        # score matrix to (0,0) with prob ~1).
        if atk_home <= 0 or def_away <= 0:
            lambda_home = league_g * home_factor
        else:
            lambda_home = league_g * (atk_home / league_a) * (def_away / league_d) * home_factor
        if atk_away <= 0 or def_home <= 0:
            lambda_away = league_g
        else:
            lambda_away = league_g * (atk_away / league_a) * (def_home / league_d)

        lambda_home, lambda_away = _apply_elo_correction(
            lambda_home, lambda_away, features.get("elo_diff", 0.0) or 0.0
        )

        return self._build_result(lambda_home, lambda_away)

    # --- Internal helpers -------------------------------------------------

    @staticmethod
    def _calibrate_home_factor(labels: pd.DataFrame) -> float:
        """Pick `home_factor` so the model's implied home-win rate matches reality.

        Cheap heuristic: empirically ~45% home wins → factor ≈ 1.2. Each 5%
        deviation moves the factor by 0.05 in the same direction. Bounded
        to [1.05, 1.40] to defend against tiny / skewed training sets.
        """
        home_win_rate = float(
            (labels["label_home_score"] > labels["label_away_score"]).mean()
        )
        # Reference: home_win_rate = 0.45 → factor = 1.20
        offset = (home_win_rate - 0.45) / 0.05 * 0.05
        return max(1.05, min(1.40, DEFAULT_HOME_FACTOR + offset))

    def _make_score_matrix(
        self, lambda_home: float, lambda_away: float
    ) -> list[list[float]]:
        """Hook so subclasses (e.g. Dixon-Coles) can apply a τ correction
        without re-implementing the rest of `_build_result`."""
        return _score_matrix(lambda_home, lambda_away, size=SCORE_MATRIX_SIZE)

    def _build_result(self, lambda_home: float, lambda_away: float) -> PredictionResult:
        score_matrix = self._make_score_matrix(lambda_home, lambda_away)
        prob_home_win, prob_draw, prob_away_win = _outcome_probs(score_matrix)
        ou_probs = _over_under_probs(score_matrix, lines=OVER_UNDER_LINES)
        btts_prob = _btts_yes_prob(score_matrix)
        top_scores = _top_k_scores(score_matrix, k=TOP_SCORES_K)

        return PredictionResult(
            prob_home_win=prob_home_win,
            prob_draw=prob_draw,
            prob_away_win=prob_away_win,
            lambda_home=float(lambda_home),
            lambda_away=float(lambda_away),
            score_matrix=score_matrix,
            top_scores=top_scores,
            over_under_probs=ou_probs,
            btts_prob=btts_prob,
        )


# --- Per-row attack / defense strength derivations ---------------------------


def _row_attack(df: pd.DataFrame, *, side: str) -> np.ndarray:
    xg_col = f"{side}_xg_avg5"
    goals_col = f"{side}_goals_scored_avg5"
    return _blend_xg_and_goals(df.get(xg_col), df.get(goals_col))


def _row_defense(df: pd.DataFrame, *, side: str) -> np.ndarray:
    xg_col = f"{side}_xg_against_avg5"
    goals_col = f"{side}_goals_conceded_avg5"
    return _blend_xg_and_goals(df.get(xg_col), df.get(goals_col))


def _blend_xg_and_goals(xg: Any, goals: Any) -> np.ndarray:
    """Return XG_WEIGHT × xG + (1 − XG_WEIGHT) × goals, NaN-safe."""
    xg_arr = pd.to_numeric(xg, errors="coerce") if xg is not None else None
    goals_arr = pd.to_numeric(goals, errors="coerce") if goals is not None else None
    if xg_arr is None and goals_arr is None:
        return np.array([], dtype=float)
    if xg_arr is None:
        return goals_arr.fillna(0.0).to_numpy(dtype=float)
    if goals_arr is None:
        return xg_arr.fillna(0.0).to_numpy(dtype=float)
    blended = XG_WEIGHT * xg_arr.fillna(goals_arr) + (1 - XG_WEIGHT) * goals_arr.fillna(xg_arr)
    return blended.fillna(0.0).to_numpy(dtype=float)


def _attack_from_features(features: dict[str, Any], side: str) -> float:
    xg = features.get(f"{side}_xg_avg5")
    goals = features.get(f"{side}_goals_scored_avg5")
    return _blend_one(xg, goals)


def _defense_from_features(features: dict[str, Any], side: str) -> float:
    xg = features.get(f"{side}_xg_against_avg5")
    goals = features.get(f"{side}_goals_conceded_avg5")
    return _blend_one(xg, goals)


def _blend_one(xg: Any, goals: Any) -> float:
    xg_v = float(xg) if xg is not None else None
    goals_v = float(goals) if goals is not None else None
    if xg_v is None and goals_v is None:
        return 0.0
    if xg_v is None:
        return goals_v or 0.0
    if goals_v is None:
        return xg_v or 0.0
    return XG_WEIGHT * xg_v + (1 - XG_WEIGHT) * goals_v


# --- Score-matrix math ------------------------------------------------------


def _score_matrix(lambda_home: float, lambda_away: float, *, size: int) -> list[list[float]]:
    """Return a `size × size` matrix where ``[i][j] = P(home=i, away=j)``.

    The matrix is renormalised so it sums exactly to 1.0 — the truncation at
    `size` drops the long Poisson tail (≈10⁻⁵ for typical λ ≈ 1.5), and we'd
    rather absorb that into the head than carry around almost-1 totals.
    """
    indices = np.arange(size)
    p_home = poisson.pmf(indices, lambda_home)
    p_away = poisson.pmf(indices, lambda_away)
    matrix = np.outer(p_home, p_away)
    total = float(matrix.sum())
    if total > 0:
        matrix = matrix / total
    return matrix.tolist()


def _outcome_probs(matrix: list[list[float]]) -> tuple[float, float, float]:
    arr = np.asarray(matrix)
    diag = float(np.trace(arr))
    upper = float(np.triu(arr, k=1).sum())  # i < j → away wins
    lower = float(np.tril(arr, k=-1).sum())  # i > j → home wins
    return lower, diag, upper


def _over_under_probs(
    matrix: list[list[float]], *, lines: tuple[float, ...]
) -> dict[str, dict[str, float]]:
    arr = np.asarray(matrix)
    n = arr.shape[0]
    i, j = np.indices((n, n))
    totals = i + j
    out: dict[str, dict[str, float]] = {}
    for line in lines:
        over = float(arr[totals > line].sum())
        out[f"{line}"] = {"over": over, "under": 1.0 - over}
    return out


def _btts_yes_prob(matrix: list[list[float]]) -> float:
    arr = np.asarray(matrix)
    return float(arr[1:, 1:].sum())


def _top_k_scores(matrix: list[list[float]], *, k: int) -> list[dict[str, Any]]:
    arr = np.asarray(matrix)
    flat = arr.flatten()
    n = arr.shape[0]
    idxs = np.argsort(-flat)[:k]
    out: list[dict[str, Any]] = []
    for idx in idxs:
        i, j = divmod(int(idx), n)
        out.append({"score": f"{i}-{j}", "prob": float(arr[i, j])})
    return out


def _apply_elo_correction(
    lambda_home: float, lambda_away: float, elo_diff: float
) -> tuple[float, float]:
    """Bump λ by ±5% when the Elo gap is meaningful (>200 in either direction)."""
    if elo_diff > ELO_THRESHOLD:
        return lambda_home * (1.0 + ELO_ADJ), lambda_away * (1.0 - ELO_ADJ)
    if elo_diff < -ELO_THRESHOLD:
        return lambda_home * (1.0 - ELO_ADJ), lambda_away * (1.0 + ELO_ADJ)
    return lambda_home, lambda_away

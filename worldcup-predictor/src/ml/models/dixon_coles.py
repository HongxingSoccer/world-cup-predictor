"""Dixon-Coles match-prediction model (Phase 4 v1).

Extends the Phase-2 :class:`PoissonBaselineModel` with two refinements taken
straight from Dixon & Coles (1997):

1. **Low-score correlation correction** — multiplies the joint Poisson PMF by
   ``τ(x, y, λ_h, λ_a, ρ)`` for the four cells ``(0,0)/(0,1)/(1,0)/(1,1)`` so
   that draws and 1-0/0-1 outcomes are no longer treated as independent.
2. **Exponential time-decay weighting** — each historical match contributes a
   weight ``w(Δt) = exp(-ξ · Δt)`` where ``Δt`` is the age of the match in
   days. This down-weights stale results when calibrating league averages.

The two parameters are exposed on the constructor; the defaults are taken
from common literature (``rho = -0.05``, ``xi = 0.0019`` ≈ a 365-day
half-life). Inference reuses the Poisson independent-grid math then applies
the τ correction before re-normalising the score matrix.

Reference: Dixon & Coles (1997) — *Modelling Association Football Scores
and Inefficiencies in the Football Betting Market*, Applied Statistics 46.
"""
from __future__ import annotations

from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Any, Optional

import numpy as np
import pandas as pd
import structlog

from src.ml.models.base import PredictionResult
from src.ml.models.poisson import (
    OVER_UNDER_LINES,
    SCORE_MATRIX_SIZE,
    TOP_SCORES_K,
    PoissonBaselineModel,
    _apply_elo_correction,
    _attack_from_features,
    _btts_yes_prob,
    _defense_from_features,
    _outcome_probs,
    _over_under_probs,
    _top_k_scores,
)

logger = structlog.get_logger(__name__)

MODEL_VERSION: str = "dixon_coles_v1"
DEFAULT_RHO: float = -0.05
DEFAULT_XI: float = 0.0019  # ~365-day half-life
RHO_BOUNDS: tuple[float, float] = (-0.2, 0.2)


class DixonColesModel(PoissonBaselineModel):
    """Poisson + Dixon-Coles τ correction + exponential time-decay weighting."""

    def __init__(
        self,
        *,
        rho: float = DEFAULT_RHO,
        xi: float = DEFAULT_XI,
        reference_date: Optional[datetime] = None,
    ) -> None:
        super().__init__()
        if not RHO_BOUNDS[0] <= rho <= RHO_BOUNDS[1]:
            raise ValueError(f"rho must be in {RHO_BOUNDS}, got {rho}")
        if xi < 0:
            raise ValueError(f"xi must be non-negative, got {xi}")
        self._rho = rho
        self._xi = xi
        self._reference_date = reference_date or datetime.now(timezone.utc)

    def get_model_version(self) -> str:
        return MODEL_VERSION

    # --- Training ---------------------------------------------------------

    def train(self, features_df: pd.DataFrame) -> None:
        """Fit baseline params using time-decay weights, then store rho/xi."""
        labels = features_df.dropna(subset=["label_home_score", "label_away_score"])
        if labels.empty:
            raise ValueError("training set has no rows with both labels populated")

        weights = compute_time_decay_weights(
            labels.get("match_date"), self._reference_date, xi=self._xi
        )
        # Weighted league-average goals: Σ(w·(g_h+g_a)/2) / Σw
        goals = (labels["label_home_score"] + labels["label_away_score"]) / 2.0
        league_avg_goals = float(np.average(goals, weights=weights))
        home_factor = self._calibrate_home_factor(labels)

        self.params = {
            "league_avg_goals": league_avg_goals,
            "league_avg_attack": league_avg_goals,
            "league_avg_defense": league_avg_goals,
            "home_factor": home_factor,
            "rho": self._rho,
            "xi": self._xi,
            "trained_on_n_matches": int(len(labels)),
            "effective_sample_size": float(weights.sum()),
        }
        logger.info("dixon_coles_trained", **self.params)

    # --- Inference --------------------------------------------------------

    def predict(self, features: dict[str, Any]) -> PredictionResult:
        if not self.params:
            raise RuntimeError("model is untrained — call .train() first")

        league_g = self.params["league_avg_goals"]
        home_factor = self.params["home_factor"]
        rho = self.params.get("rho", self._rho)

        atk_home = _attack_from_features(features, "home") or league_g
        atk_away = _attack_from_features(features, "away") or league_g
        def_home = _defense_from_features(features, "home") or league_g
        def_away = _defense_from_features(features, "away") or league_g

        lambda_home = home_factor * (atk_home / league_g) * (def_away / league_g) * league_g
        lambda_away = (atk_away / league_g) * (def_home / league_g) * league_g
        lambda_home, lambda_away = _apply_elo_correction(
            lambda_home, lambda_away, features.get("elo_diff", 0.0) or 0.0
        )

        matrix = dixon_coles_score_matrix(
            lambda_home, lambda_away, rho=rho, size=SCORE_MATRIX_SIZE
        )
        return _build_prediction_result(matrix, lambda_home, lambda_away)


# --- Public helpers (also used by ensemble + tests) -------------------------


def compute_time_decay_weights(
    dates: Any, reference: datetime, *, xi: float
) -> np.ndarray:
    """Return ``exp(-xi · Δdays)`` weights, one per row, never below 1e-6.

    ``dates`` may be ``None`` or contain NaT — those rows fall back to
    weight 1.0 so a feature DataFrame without ``match_date`` still trains.
    """
    if dates is None or xi == 0:
        n = 0 if dates is None else len(dates)
        return np.ones(n, dtype=float) if n else np.array([1.0])
    series = pd.to_datetime(dates, utc=True, errors="coerce")
    ref = pd.Timestamp(reference).tz_convert("UTC") if reference.tzinfo else pd.Timestamp(reference, tz="UTC")
    delta_days = (ref - series).dt.total_seconds() / 86400.0
    delta_days = delta_days.fillna(0.0).clip(lower=0.0).to_numpy(dtype=float)
    weights = np.exp(-xi * delta_days)
    return np.clip(weights, 1e-6, 1.0)


def dixon_coles_tau(
    x: int, y: int, lambda_home: float, lambda_away: float, rho: float
) -> float:
    """Return the Dixon-Coles τ adjustment for one (x, y) cell.

    Only the four low-score cells are corrected; everything else returns 1.
    """
    if x == 0 and y == 0:
        return 1.0 - lambda_home * lambda_away * rho
    if x == 0 and y == 1:
        return 1.0 + lambda_home * rho
    if x == 1 and y == 0:
        return 1.0 + lambda_away * rho
    if x == 1 and y == 1:
        return 1.0 - rho
    return 1.0


def dixon_coles_score_matrix(
    lambda_home: float, lambda_away: float, *, rho: float, size: int
) -> list[list[float]]:
    """Return a renormalised ``size × size`` matrix with τ correction applied."""
    from scipy.stats import poisson

    indices = np.arange(size)
    p_home = poisson.pmf(indices, lambda_home)
    p_away = poisson.pmf(indices, lambda_away)
    matrix = np.outer(p_home, p_away)

    tau = np.ones((size, size), dtype=float)
    tau[0, 0] = max(1e-9, 1.0 - lambda_home * lambda_away * rho)
    tau[0, 1] = max(1e-9, 1.0 + lambda_home * rho)
    tau[1, 0] = max(1e-9, 1.0 + lambda_away * rho)
    tau[1, 1] = max(1e-9, 1.0 - rho)
    matrix = matrix * tau

    total = float(matrix.sum())
    if total > 0:
        matrix = matrix / total
    return matrix.tolist()


def _build_prediction_result(
    matrix: list[list[float]], lambda_home: float, lambda_away: float
) -> PredictionResult:
    prob_home, prob_draw, prob_away = _outcome_probs(matrix)
    return PredictionResult(
        prob_home_win=prob_home,
        prob_draw=prob_draw,
        prob_away_win=prob_away,
        lambda_home=float(lambda_home),
        lambda_away=float(lambda_away),
        score_matrix=matrix,
        top_scores=_top_k_scores(matrix, k=TOP_SCORES_K),
        over_under_probs=_over_under_probs(matrix, lines=OVER_UNDER_LINES),
        btts_prob=_btts_yes_prob(matrix),
    )


# ---------------------------------------------------------------------------
# Weighted MLE (design §2.1.3)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DixonColesParams:
    """Optimised parameters: per-team attack/defence + global γ (home), ρ."""

    attack: dict[str, float]
    defence: dict[str, float]
    home_advantage: float
    rho: float
    log_likelihood: float
    n_matches: int


def optimize_dc_params(
    matches_df: pd.DataFrame,
    *,
    rho_init: float = DEFAULT_RHO,
    home_init: float = 1.3,
    xi: float = DEFAULT_XI,
    reference: Optional[datetime] = None,
    max_iter: int = 200,
) -> DixonColesParams:
    """Fit Dixon-Coles parameters via weighted MLE (scipy L-BFGS-B).

    The DataFrame must contain ``home_team``, ``away_team``,
    ``label_home_score``, ``label_away_score`` and (optionally) ``match_date``.

    Returns a :class:`DixonColesParams` object the caller can plug into
    :func:`dixon_coles_score_matrix`. Designed for offline calibration only —
    inference uses the lighter-weight :class:`DixonColesModel`.
    """
    from scipy.optimize import minimize  # noqa: WPS433 — heavy import isolated

    df = matches_df.dropna(
        subset=["home_team", "away_team", "label_home_score", "label_away_score"]
    )
    if df.empty:
        raise ValueError("optimize_dc_params: empty training set")

    teams = sorted(set(df["home_team"]).union(df["away_team"]))
    team_index = {t: i for i, t in enumerate(teams)}
    n_teams = len(teams)
    home_idx = df["home_team"].map(team_index).to_numpy(dtype=int)
    away_idx = df["away_team"].map(team_index).to_numpy(dtype=int)
    home_goals = df["label_home_score"].to_numpy(dtype=int)
    away_goals = df["label_away_score"].to_numpy(dtype=int)
    weights = compute_time_decay_weights(
        df.get("match_date"), reference or datetime.now(timezone.utc), xi=xi
    )
    if len(weights) != len(df):
        weights = np.ones(len(df), dtype=float)

    # Parameter packing: [attack_0..attack_{N-1}, defence_0..defence_{N-1}, γ, ρ]
    init_params = np.concatenate(
        [np.zeros(n_teams), np.zeros(n_teams), [np.log(home_init), rho_init]]
    )
    # Constrain Σ attack = 0 by adding a soft penalty (cheap & robust).

    def _neg_log_likelihood(params: np.ndarray) -> float:
        attack = params[:n_teams]
        defence = params[n_teams : 2 * n_teams]
        gamma = float(params[-2])
        rho = float(np.clip(params[-1], RHO_BOUNDS[0], RHO_BOUNDS[1]))
        lambda_h = np.exp(gamma + attack[home_idx] + defence[away_idx])
        lambda_a = np.exp(attack[away_idx] + defence[home_idx])
        lambda_h = np.clip(lambda_h, 1e-6, 20.0)
        lambda_a = np.clip(lambda_a, 1e-6, 20.0)
        log_p = (
            home_goals * np.log(lambda_h)
            - lambda_h
            - _gammaln_int(home_goals)
            + away_goals * np.log(lambda_a)
            - lambda_a
            - _gammaln_int(away_goals)
        )
        log_tau = _vector_log_tau(home_goals, away_goals, lambda_h, lambda_a, rho)
        weighted = weights * (log_p + log_tau)
        attack_penalty = 1e3 * (attack.sum() ** 2)  # identifiability constraint
        return float(-weighted.sum() + attack_penalty)

    result = minimize(
        _neg_log_likelihood,
        init_params,
        method="L-BFGS-B",
        options={"maxiter": max_iter, "disp": False},
    )
    if not result.success:
        logger.warning("dc_mle_did_not_converge", message=result.message)

    attack_arr = result.x[:n_teams]
    defence_arr = result.x[n_teams : 2 * n_teams]
    gamma = float(result.x[-2])
    rho = float(np.clip(result.x[-1], RHO_BOUNDS[0], RHO_BOUNDS[1]))
    return DixonColesParams(
        attack={t: float(attack_arr[i]) for t, i in team_index.items()},
        defence={t: float(defence_arr[i]) for t, i in team_index.items()},
        home_advantage=float(np.exp(gamma)),
        rho=rho,
        log_likelihood=float(-result.fun),
        n_matches=int(len(df)),
    )


def _gammaln_int(values: np.ndarray) -> np.ndarray:
    """log(k!) for non-negative integers via ``scipy.special.gammaln(k + 1)``."""
    from scipy.special import gammaln  # noqa: WPS433

    return gammaln(values.astype(float) + 1.0)


def _vector_log_tau(
    home_goals: np.ndarray,
    away_goals: np.ndarray,
    lambda_h: np.ndarray,
    lambda_a: np.ndarray,
    rho: float,
) -> np.ndarray:
    """Vectorised log τ correction; only the 4 low-score cells deviate from 0."""
    tau = np.ones_like(lambda_h)
    cell_00 = (home_goals == 0) & (away_goals == 0)
    cell_01 = (home_goals == 0) & (away_goals == 1)
    cell_10 = (home_goals == 1) & (away_goals == 0)
    cell_11 = (home_goals == 1) & (away_goals == 1)
    tau[cell_00] = np.maximum(1e-9, 1.0 - lambda_h[cell_00] * lambda_a[cell_00] * rho)
    tau[cell_01] = np.maximum(1e-9, 1.0 + lambda_h[cell_01] * rho)
    tau[cell_10] = np.maximum(1e-9, 1.0 + lambda_a[cell_10] * rho)
    tau[cell_11] = max(1e-9, 1.0 - rho)
    return np.log(tau)


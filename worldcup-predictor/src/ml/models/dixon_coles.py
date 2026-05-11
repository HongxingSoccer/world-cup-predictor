"""Dixon-Coles match-prediction model.

Extends :class:`PoissonBaselineModel` with the Dixon & Coles (1997) low-score
correction. Two independent Poissons over-predict 0-0 / 0-1 / 1-0 / 1-1 in
real football data; DC scales those four cells by

    τ(0,0) = 1 − λ_h · λ_a · ρ
    τ(0,1) = 1 + λ_h · ρ
    τ(1,0) = 1 + λ_a · ρ
    τ(1,1) = 1 − ρ

with τ = 1 elsewhere. ρ is learned via 1-D maximum likelihood on the same
training rows that calibrated the Poisson side. We bound ρ to ``[-0.2, 0.2]``
so τ stays positive across plausible λ ≤ 5.

The Phase-2 lambda-derivation path (attack × defense × home_factor) is
unchanged — :class:`DixonColesModel` only overrides :meth:`_make_score_matrix`
and adds ρ-fitting on top of the Poisson trainer. An optional weighted
per-team MLE (:func:`optimize_dc_params`) is kept as a Phase-4 utility for
when we want a fully independent attack/defence parameter set.

Reference: Dixon & Coles (1997) — *Modelling Association Football Scores
and Inefficiencies in the Football Betting Market*, Applied Statistics 46.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import numpy as np
import pandas as pd
import structlog
from scipy.optimize import minimize_scalar
from scipy.stats import poisson as poisson_dist

from src.ml.models.poisson import (
    SCORE_MATRIX_SIZE,
    PoissonBaselineModel,
    _apply_elo_correction,
    _attack_from_features,
    _defense_from_features,
)

logger = structlog.get_logger(__name__)

MODEL_VERSION: str = "dixon_coles_v1"
DEFAULT_RHO: float = -0.05  # mild negative correlation as a sane prior
DEFAULT_XI: float = 0.0019  # ~365-day half-life (used by optimize_dc_params)
RHO_BOUNDS: tuple[float, float] = (-0.2, 0.2)


class DixonColesModel(PoissonBaselineModel):
    """Poisson + Dixon-Coles τ correction (single ρ parameter)."""

    def __init__(
        self, *, rho: float | None = None, xi: float | None = None
    ) -> None:
        super().__init__()
        if rho is not None and not (RHO_BOUNDS[0] <= rho <= RHO_BOUNDS[1]):
            raise ValueError(f"rho must lie in {RHO_BOUNDS}; got {rho}")
        if xi is not None and xi < 0:
            raise ValueError(f"xi must be >= 0; got {xi}")
        self._fixed_rho = rho
        self._xi = xi

    def get_model_version(self) -> str:
        return MODEL_VERSION

    # --- Training ---------------------------------------------------------

    def train(self, features_df: pd.DataFrame) -> None:
        """Fit Poisson params via ``super().train``, then a 1-D MLE for ρ."""
        super().train(features_df)
        rho = self._fixed_rho if self._fixed_rho is not None else self._fit_rho(features_df)
        self.params["rho"] = rho
        logger.info(
            "dixon_coles_trained",
            rho=rho,
            league_avg_goals=self.params["league_avg_goals"],
            home_factor=self.params["home_factor"],
            trained_on_n_matches=self.params["trained_on_n_matches"],
        )

    # --- Inference --------------------------------------------------------

    def _make_score_matrix(
        self, lambda_home: float, lambda_away: float
    ) -> list[list[float]]:
        rho = float(self.params.get("rho", DEFAULT_RHO))
        return dixon_coles_score_matrix(
            lambda_home, lambda_away, rho=rho, size=SCORE_MATRIX_SIZE
        )

    # --- Internal helpers -------------------------------------------------

    def _fit_rho(self, features_df: pd.DataFrame) -> float:
        """One-dim MLE for ρ given the calibrated λ predictions on training rows.

        We compute (λ_h, λ_a) per training row using the just-trained Poisson
        params (same path inference uses), then pick ρ ∈ ``RHO_BOUNDS`` that
        maximises the log-likelihood of the actual scores under the
        DC-corrected joint distribution.
        """
        labels = features_df.dropna(subset=["label_home_score", "label_away_score"])
        if labels.empty:
            return DEFAULT_RHO

        lambda_pairs: list[tuple[float, float, int, int]] = []
        for _, row in labels.iterrows():
            lh, la = self._row_lambdas(row)
            lambda_pairs.append(
                (lh, la, int(row["label_home_score"]), int(row["label_away_score"]))
            )

        # Pre-compute the Poisson PMF terms once — they don't depend on ρ.
        pmf_terms = [
            float(poisson_dist.pmf(hs, lh) * poisson_dist.pmf(as_, la))
            for lh, la, hs, as_ in lambda_pairs
        ]

        def neg_log_lik(rho: float) -> float:
            total = 0.0
            for (lh, la, hs, as_), pmf in zip(lambda_pairs, pmf_terms):
                tau = dixon_coles_tau(hs, as_, lh, la, rho)
                if tau <= 0 or pmf <= 0:
                    return 1e9  # outside the feasible region
                total -= np.log(tau * pmf)
            return total

        result = minimize_scalar(
            neg_log_lik, bounds=RHO_BOUNDS, method="bounded", options={"xatol": 1e-4}
        )
        return float(result.x) if result.success else DEFAULT_RHO

    def _row_lambdas(self, row: pd.Series) -> tuple[float, float]:
        """Replay :meth:`PoissonBaselineModel.predict`'s lambda derivation on
        a single training row. We don't need the full PredictionResult during
        ρ fitting — just (λ_h, λ_a)."""
        params = self.params
        league_g = float(params["league_avg_goals"])
        league_a = float(params["league_avg_attack"])
        league_d = float(params["league_avg_defense"])
        home_factor = float(params["home_factor"])

        feats = row.to_dict()
        atk_h = _attack_from_features(feats, "home")
        atk_a = _attack_from_features(feats, "away")
        def_h = _defense_from_features(feats, "home")
        def_a = _defense_from_features(feats, "away")

        if atk_h <= 0 or def_a <= 0:
            lh = league_g * home_factor
        else:
            lh = league_g * (atk_h / league_a) * (def_a / league_d) * home_factor
        if atk_a <= 0 or def_h <= 0:
            la = league_g
        else:
            la = league_g * (atk_a / league_a) * (def_h / league_d)

        elo_diff = float(feats.get("elo_diff", 0.0) or 0.0)
        return _apply_elo_correction(lh, la, elo_diff)


# --- Public helpers ---------------------------------------------------------


def dixon_coles_tau(
    x: int, y: int, lambda_home: float, lambda_away: float, rho: float
) -> float:
    """Return the Dixon-Coles τ adjustment for one (x, y) cell.

    τ = 1 outside the four low-score cells, so callers can wrap this without
    a special-case path."""
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
    """Return a renormalised ``size × size`` matrix with τ correction applied.

    Negative τ values (which can happen for ρ outside the safe bound at
    extreme λ) are clamped to a tiny positive number — they're a sign of
    an over-aggressive ρ rather than a real probability and would otherwise
    produce negative cell probabilities downstream."""
    indices = np.arange(size)
    p_home = poisson_dist.pmf(indices, lambda_home)
    p_away = poisson_dist.pmf(indices, lambda_away)
    matrix = np.outer(p_home, p_away)

    matrix[0, 0] *= max(1e-9, 1.0 - lambda_home * lambda_away * rho)
    matrix[0, 1] *= max(1e-9, 1.0 + lambda_home * rho)
    matrix[1, 0] *= max(1e-9, 1.0 + lambda_away * rho)
    matrix[1, 1] *= max(1e-9, 1.0 - rho)

    total = float(matrix.sum())
    if total > 0:
        matrix = matrix / total
    return matrix.tolist()


def compute_time_decay_weights(
    dates: Any, reference: datetime, *, xi: float, n_rows: int | None = None
) -> np.ndarray:
    """Return ``exp(-xi · Δdays)`` weights, one per row, never below 1e-6.

    Used by :func:`optimize_dc_params` for weighted MLE. ``dates`` may be
    ``None`` or contain NaT — those rows fall back to weight 1.0 so a
    feature DataFrame without ``match_date`` still trains. When ``dates`` is
    ``None``, pass ``n_rows`` to receive one weight per row; if neither is
    available, this function preserves the legacy fallback of returning
    ``np.array([1.0])``.
    """
    if dates is None:
        return np.ones(n_rows, dtype=float) if n_rows else np.array([1.0])
    if xi == 0:
        n = len(dates)
        return np.ones(n, dtype=float) if n else (
            np.ones(n_rows, dtype=float) if n_rows else np.array([1.0])
        )
    series = pd.to_datetime(dates, utc=True, errors="coerce")
    ref = (
        pd.Timestamp(reference).tz_convert("UTC")
        if reference.tzinfo
        else pd.Timestamp(reference, tz="UTC")
    )
    delta_days = (ref - series).dt.total_seconds() / 86400.0
    delta_days = delta_days.fillna(0.0).clip(lower=0.0).to_numpy(dtype=float)
    weights = np.exp(-xi * delta_days)
    return np.clip(weights, 1e-6, 1.0)


# ---------------------------------------------------------------------------
# Per-team weighted MLE (Phase-4 advanced calibration; unused at inference)
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
    reference: datetime | None = None,
    max_iter: int = 200,
) -> DixonColesParams:
    """Fit Dixon-Coles parameters via weighted MLE (scipy L-BFGS-B).

    The DataFrame must contain ``home_team``, ``away_team``,
    ``label_home_score``, ``label_away_score`` and (optionally) ``match_date``.
    Designed for offline calibration only — :class:`DixonColesModel` reuses
    the lighter Poisson-derived λ during inference."""
    from scipy.optimize import minimize  # heavy import isolated

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
        df.get("match_date"), reference or datetime.now(UTC), xi=xi
    )
    if len(weights) != len(df):
        weights = np.ones(len(df), dtype=float)

    init_params = np.concatenate(
        [np.zeros(n_teams), np.zeros(n_teams), [np.log(home_init), rho_init]]
    )

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
        n_matches=len(df),
    )


def _gammaln_int(values: np.ndarray) -> np.ndarray:
    from scipy.special import gammaln  # heavy import isolated

    return gammaln(values.astype(float) + 1.0)


def _vector_log_tau(
    home_goals: np.ndarray,
    away_goals: np.ndarray,
    lambda_h: np.ndarray,
    lambda_a: np.ndarray,
    rho: float,
) -> np.ndarray:
    """Vectorised log τ correction; only the four low-score cells deviate from 0."""
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

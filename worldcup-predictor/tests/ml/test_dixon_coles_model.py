"""Unit tests for `DixonColesModel` and the τ-correction helpers."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.ml.models.dixon_coles import (
    DEFAULT_RHO,
    DixonColesModel,
    dixon_coles_score_matrix,
    dixon_coles_tau,
)


def _toy_training_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "home_xg_avg5": [1.5, 1.0, 2.0, 1.8],
            "away_xg_avg5": [1.0, 1.2, 0.8, 1.5],
            "home_goals_scored_avg5": [1.5, 1.0, 2.0, 1.5],
            "away_goals_scored_avg5": [1.0, 1.2, 0.8, 1.5],
            "home_xg_against_avg5": [1.0, 1.5, 0.5, 1.2],
            "away_xg_against_avg5": [1.5, 1.0, 1.5, 1.5],
            "home_goals_conceded_avg5": [1.0, 1.5, 0.5, 1.2],
            "away_goals_conceded_avg5": [1.5, 1.0, 1.5, 1.5],
            "label_home_score": [2, 1, 3, 2],
            "label_away_score": [1, 1, 0, 2],
        }
    )


def _balanced_features() -> dict[str, float]:
    return {
        "home_xg_avg5": 1.5, "away_xg_avg5": 1.5,
        "home_goals_scored_avg5": 1.5, "away_goals_scored_avg5": 1.5,
        "home_xg_against_avg5": 1.5, "away_xg_against_avg5": 1.5,
        "home_goals_conceded_avg5": 1.5, "away_goals_conceded_avg5": 1.5,
        "elo_diff": 0.0,
    }


def test_tau_returns_one_outside_low_score_cells():
    # τ = 1 everywhere except the four (i, j) ∈ {(0,0),(0,1),(1,0),(1,1)} cells.
    for x, y in [(2, 0), (0, 2), (3, 3), (5, 1), (1, 4)]:
        assert dixon_coles_tau(x, y, 1.5, 1.2, rho=-0.05) == 1.0


def test_tau_low_score_cells_match_dixon_coles_formula():
    lh, la, rho = 1.4, 1.1, -0.05
    assert dixon_coles_tau(0, 0, lh, la, rho) == pytest.approx(1.0 - lh * la * rho)
    assert dixon_coles_tau(0, 1, lh, la, rho) == pytest.approx(1.0 + lh * rho)
    assert dixon_coles_tau(1, 0, lh, la, rho) == pytest.approx(1.0 + la * rho)
    assert dixon_coles_tau(1, 1, lh, la, rho) == pytest.approx(1.0 - rho)


def test_score_matrix_renormalises_to_one():
    matrix = dixon_coles_score_matrix(1.4, 1.1, rho=-0.1, size=10)
    total = sum(sum(row) for row in matrix)
    assert total == pytest.approx(1.0, abs=1e-9)


def test_negative_rho_increases_00_and_11_relative_to_independent_poisson():
    # The classic Dixon-Coles 1997 sign convention: ρ < 0 implies the data has
    # MORE 0-0 / 1-1 than independent Poisson predicts (defensive correlation).
    # τ(0,0) = 1 - λ_h·λ_a·ρ → > 1 when ρ < 0 → 0-0 cell scaled UP before renorm.
    lh, la = 1.5, 1.2
    independent = dixon_coles_score_matrix(lh, la, rho=0.0, size=10)
    negative = dixon_coles_score_matrix(lh, la, rho=-0.1, size=10)
    assert negative[0][0] > independent[0][0]
    assert negative[1][1] > independent[1][1]
    # And it pulls AWAY from 0-1 / 1-0 (which got τ < 1 when ρ < 0).
    assert negative[0][1] < independent[0][1]
    assert negative[1][0] < independent[1][0]


def test_train_fits_rho_within_bounds():
    m = DixonColesModel()
    m.train(_toy_training_frame())
    rho = m.params["rho"]
    assert -0.2 <= rho <= 0.2


def test_predict_inherits_lambda_path_from_poisson():
    """ρ correction must not change the marginal expected goals materially —
    the τ adjustment redistributes within the joint, but Σ(i · P(i, j)) over
    the matrix should still ≈ λ_home (within numerical truncation)."""
    m = DixonColesModel()
    m.train(_toy_training_frame())
    pred = m.predict(_balanced_features())

    arr = np.asarray(pred.score_matrix)
    n = arr.shape[0]
    expected_home_goals = float((arr * np.arange(n)[:, None]).sum())
    expected_away_goals = float((arr * np.arange(n)[None, :]).sum())
    # Allow some leeway: τ correction shifts mass between low cells, which
    # nudges the marginals slightly. λ ≈ 1.5 and we accept ±0.15.
    assert abs(expected_home_goals - pred.lambda_home) < 0.2
    assert abs(expected_away_goals - pred.lambda_away) < 0.2


def test_predict_outcome_probs_sum_to_one():
    m = DixonColesModel()
    m.train(_toy_training_frame())
    pred = m.predict(_balanced_features())
    total = pred.prob_home_win + pred.prob_draw + pred.prob_away_win
    assert total == pytest.approx(1.0, abs=1e-6)


def test_untrained_model_raises():
    m = DixonColesModel()
    with pytest.raises(RuntimeError, match="untrained"):
        m.predict(_balanced_features())


def test_default_rho_used_when_params_missing_rho_key():
    """Belt-and-suspenders: a model loaded from an older artifact without ρ
    in `self.params` should fall back to ``DEFAULT_RHO`` instead of
    KeyError'ing inside ``_make_score_matrix``."""
    m = DixonColesModel()
    # Manually populate Poisson params (no ρ) — simulates loading an older
    # serialised model.
    m.params = {
        "league_avg_goals": 1.4,
        "league_avg_attack": 0.6,
        "league_avg_defense": 0.6,
        "home_factor": 1.2,
        "trained_on_n_matches": 100,
    }
    pred = m.predict(_balanced_features())  # no ρ key — must not raise
    assert pred.lambda_home > 0
    # Sanity: matrix used DEFAULT_RHO.
    matrix_with_default = dixon_coles_score_matrix(
        pred.lambda_home, pred.lambda_away, rho=DEFAULT_RHO, size=10
    )
    # The two matrices should match cell-by-cell.
    for i in range(10):
        for j in range(10):
            assert pred.score_matrix[i][j] == pytest.approx(matrix_with_default[i][j])

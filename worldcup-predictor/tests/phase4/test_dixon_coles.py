"""Unit tests for src.ml.models.dixon_coles."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from src.ml.models.dixon_coles import (
    DEFAULT_RHO,
    DixonColesModel,
    compute_time_decay_weights,
    dixon_coles_score_matrix,
    dixon_coles_tau,
)


def _build_training_df(n: int = 50) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    base = datetime(2024, 1, 1, tzinfo=UTC)
    rows = []
    for i in range(n):
        rows.append(
            {
                "match_date": base + timedelta(days=i * 3),
                "home_xg_avg5": float(rng.uniform(0.8, 2.5)),
                "away_xg_avg5": float(rng.uniform(0.5, 2.0)),
                "home_goals_scored_avg5": float(rng.uniform(0.5, 2.5)),
                "away_goals_scored_avg5": float(rng.uniform(0.4, 2.0)),
                "home_xg_against_avg5": float(rng.uniform(0.5, 1.8)),
                "away_xg_against_avg5": float(rng.uniform(0.5, 1.8)),
                "home_goals_conceded_avg5": float(rng.uniform(0.5, 1.8)),
                "away_goals_conceded_avg5": float(rng.uniform(0.5, 1.8)),
                "elo_diff": float(rng.uniform(-300, 300)),
                "label_home_score": int(rng.integers(0, 4)),
                "label_away_score": int(rng.integers(0, 4)),
            }
        )
    return pd.DataFrame(rows)


def test_tau_default_cells_unchanged_for_non_lowscore():
    assert dixon_coles_tau(2, 3, 1.5, 1.2, DEFAULT_RHO) == 1.0
    assert dixon_coles_tau(0, 2, 1.5, 1.2, DEFAULT_RHO) == 1.0


def test_tau_low_score_cells_adjust_with_negative_rho():
    rho = -0.1
    # With negative rho, the (0,0) and (1,1) tau > 1 → boost draws
    assert dixon_coles_tau(0, 0, 1.0, 1.0, rho) > 1.0
    assert dixon_coles_tau(1, 1, 1.0, 1.0, rho) > 1.0
    # And (0,1)/(1,0) get tau < 1
    assert dixon_coles_tau(0, 1, 1.0, 1.0, rho) < 1.0
    assert dixon_coles_tau(1, 0, 1.0, 1.0, rho) < 1.0


def test_score_matrix_normalises_to_one():
    matrix = dixon_coles_score_matrix(1.5, 1.2, rho=DEFAULT_RHO, size=10)
    total = sum(p for row in matrix for p in row)
    assert total == pytest.approx(1.0, abs=1e-9)


def test_time_decay_weights_recent_higher_than_old():
    ref = datetime(2024, 6, 1, tzinfo=UTC)
    dates = pd.Series([
        datetime(2023, 6, 1, tzinfo=UTC),  # 365 days old
        datetime(2024, 5, 25, tzinfo=UTC),  # 7 days old
    ])
    weights = compute_time_decay_weights(dates, ref, xi=0.0019)
    assert weights[1] > weights[0]
    assert weights[0] > 0


def test_train_then_predict_returns_consistent_probs():
    model = DixonColesModel()
    model.train(_build_training_df())
    features = {
        "home_xg_avg5": 1.6,
        "away_xg_avg5": 1.1,
        "home_goals_scored_avg5": 1.5,
        "away_goals_scored_avg5": 1.0,
        "home_xg_against_avg5": 1.0,
        "away_xg_against_avg5": 1.2,
        "home_goals_conceded_avg5": 1.0,
        "away_goals_conceded_avg5": 1.2,
        "elo_diff": 100.0,
    }
    result = model.predict(features)
    total = result.prob_home_win + result.prob_draw + result.prob_away_win
    assert total == pytest.approx(1.0, abs=1e-6)
    assert 0.0 <= result.btts_prob <= 1.0
    assert len(result.score_matrix) == 10


def test_constructor_rejects_invalid_params():
    with pytest.raises(ValueError):
        DixonColesModel(rho=10.0)
    with pytest.raises(ValueError):
        DixonColesModel(xi=-1.0)


def test_predict_without_training_raises():
    with pytest.raises(RuntimeError):
        DixonColesModel().predict({})

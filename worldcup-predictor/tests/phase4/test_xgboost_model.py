"""Unit tests for src.ml.models.xgboost_model."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.ml.models.xgboost_model import DEFAULT_FEATURES, XGBoostMatchModel


def _training_df(n: int = 200) -> pd.DataFrame:
    rng = np.random.default_rng(7)
    rows = []
    for _ in range(n):
        elo_diff = float(rng.uniform(-400, 400))
        # Bias scoring toward Elo to give the model a learnable signal.
        home_score = max(0, int(rng.normal(1.5 + elo_diff / 600, 1.0)))
        away_score = max(0, int(rng.normal(1.5 - elo_diff / 600, 1.0)))
        row = {col: float(rng.uniform(0.5, 2.5)) for col in DEFAULT_FEATURES}
        row["elo_diff"] = elo_diff
        row["label_home_score"] = home_score
        row["label_away_score"] = away_score
        rows.append(row)
    return pd.DataFrame(rows)


def test_train_and_predict_outcome_probs_normalised():
    model = XGBoostMatchModel(n_estimators=30, max_depth=3)
    model.train(_training_df())
    features = {col: 1.5 for col in DEFAULT_FEATURES}
    features["elo_diff"] = 200.0
    result = model.predict(features)
    total = result.prob_home_win + result.prob_draw + result.prob_away_win
    assert total == pytest.approx(1.0, abs=1e-6)
    assert len(result.score_matrix) == 10


def test_predict_without_training_raises():
    with pytest.raises(RuntimeError):
        XGBoostMatchModel().predict({col: 1.0 for col in DEFAULT_FEATURES})


def test_score_matrix_marginals_match_outcome_probs():
    model = XGBoostMatchModel(n_estimators=30, max_depth=3)
    model.train(_training_df())
    features = {col: 1.2 for col in DEFAULT_FEATURES}
    features["elo_diff"] = -150.0
    result = model.predict(features)
    arr = np.asarray(result.score_matrix)
    home_marginal = float(np.tril(arr, k=-1).sum())
    draw_marginal = float(np.trace(arr))
    away_marginal = float(np.triu(arr, k=1).sum())
    assert home_marginal == pytest.approx(result.prob_home_win, abs=1e-6)
    assert draw_marginal == pytest.approx(result.prob_draw, abs=1e-6)
    assert away_marginal == pytest.approx(result.prob_away_win, abs=1e-6)

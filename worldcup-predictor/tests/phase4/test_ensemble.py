"""Unit tests for src.ml.models.ensemble."""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import pytest

from src.ml.models.base import BasePredictionModel, PredictionResult
from src.ml.models.ensemble import EnsembleModel


class _FixedModel(BasePredictionModel):
    """Minimal model that returns a hard-coded result regardless of features."""

    def __init__(self, version: str, prob_home: float, prob_draw: float, prob_away: float):
        super().__init__()
        self._version = version
        self._prob_home = prob_home
        self._prob_draw = prob_draw
        self._prob_away = prob_away

    def get_model_version(self) -> str:
        return self._version

    def train(self, features_df: pd.DataFrame) -> None:
        self.params = {"trained_on_n_matches": int(len(features_df))}

    def predict(self, features: dict[str, Any]) -> PredictionResult:
        n = 10
        matrix = np.zeros((n, n))
        # Concentrate mass deterministically: 1-0 home, 0-0 draw, 0-1 away
        matrix[1, 0] = self._prob_home
        matrix[0, 0] = self._prob_draw
        matrix[0, 1] = self._prob_away
        total = float(matrix.sum())
        if total > 0:
            matrix = matrix / total
        return PredictionResult(
            prob_home_win=self._prob_home,
            prob_draw=self._prob_draw,
            prob_away_win=self._prob_away,
            lambda_home=1.5,
            lambda_away=1.0,
            score_matrix=matrix.tolist(),
            top_scores=[],
            over_under_probs={},
            btts_prob=0.0,
        )


def test_ensemble_averages_with_equal_weights():
    a = _FixedModel("a", 0.6, 0.2, 0.2)
    b = _FixedModel("b", 0.2, 0.2, 0.6)
    ens = EnsembleModel([a, b], weights=[1.0, 1.0])
    res = ens.predict({})
    assert res.prob_home_win == pytest.approx(0.4, abs=1e-6)
    assert res.prob_away_win == pytest.approx(0.4, abs=1e-6)
    assert res.prob_draw == pytest.approx(0.2, abs=1e-6)


def test_ensemble_weights_normalise_correctly():
    a = _FixedModel("a", 0.8, 0.1, 0.1)
    b = _FixedModel("b", 0.1, 0.1, 0.8)
    ens = EnsembleModel([a, b], weights=[3.0, 1.0])
    res = ens.predict({})
    # 0.75 * 0.8 + 0.25 * 0.1 = 0.625
    assert res.prob_home_win == pytest.approx(0.625, abs=1e-6)


def test_constructor_rejects_invalid_input():
    a = _FixedModel("a", 0.5, 0.3, 0.2)
    with pytest.raises(ValueError):
        EnsembleModel([], weights=[])
    with pytest.raises(ValueError):
        EnsembleModel([a], weights=[1.0, 2.0])
    with pytest.raises(ValueError):
        EnsembleModel([a], weights=[-1.0])
    with pytest.raises(ValueError):
        EnsembleModel([a], weights=[0.0])


def test_train_propagates_to_sub_models():
    a = _FixedModel("a", 0.4, 0.3, 0.3)
    b = _FixedModel("b", 0.4, 0.3, 0.3)
    ens = EnsembleModel([a, b], weights=[1.0, 1.0])
    ens.train(pd.DataFrame({"x": [1, 2, 3]}))
    assert a.params["trained_on_n_matches"] == 3
    assert b.params["trained_on_n_matches"] == 3

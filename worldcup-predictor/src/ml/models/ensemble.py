"""Weighted-average ensemble combiner (Phase 4 v1).

Takes any number of bound :class:`BasePredictionModel` instances plus a
weight vector and produces a single :class:`PredictionResult`. Each
sub-model's score matrix is averaged element-wise with its weight; the
1x2 / over-under / BTTS / top-scores aggregates are recomputed from the
fused matrix so they remain internally consistent.

Default composition: 25% Poisson baseline, 35% Dixon-Coles, 40% XGBoost
— biased toward the data-driven models while keeping the Poisson floor
as a sanity anchor.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import structlog

from src.ml.models.base import BasePredictionModel, PredictionResult
from src.ml.models.dixon_coles import _build_prediction_result

logger = structlog.get_logger(__name__)

MODEL_VERSION: str = "ensemble_v1"


class EnsembleModel(BasePredictionModel):
    """Weighted average of N sub-models, each producing a score matrix."""

    def __init__(
        self,
        models: list[BasePredictionModel],
        weights: list[float],
    ) -> None:
        super().__init__()
        if len(models) != len(weights):
            raise ValueError(
                f"models / weights size mismatch: {len(models)} vs {len(weights)}"
            )
        if not models:
            raise ValueError("ensemble requires at least one sub-model")
        if any(w < 0 for w in weights):
            raise ValueError(f"weights must be non-negative: {weights}")
        total = float(sum(weights))
        if total <= 0:
            raise ValueError("weights must sum to a positive value")
        self._models = models
        self._weights = [float(w) / total for w in weights]
        self.params = {
            "sub_versions": [m.get_model_version() for m in models],
            "weights": self._weights,
        }

    def get_model_version(self) -> str:
        return MODEL_VERSION

    def train(self, features_df: pd.DataFrame) -> None:
        """Train each sub-model independently on the same DataFrame."""
        for model in self._models:
            model.train(features_df)
        self.params["trained_on_n_matches"] = int(len(features_df))
        logger.info("ensemble_trained", **self.params)

    def predict(self, features: dict[str, Any]) -> PredictionResult:
        sub_results = [m.predict(features) for m in self._models]
        matrix = _weighted_matrix_average(sub_results, self._weights)
        lambda_home = sum(w * r.lambda_home for w, r in zip(self._weights, sub_results))
        lambda_away = sum(w * r.lambda_away for w, r in zip(self._weights, sub_results))
        return _build_prediction_result(matrix, lambda_home, lambda_away)


def _weighted_matrix_average(
    results: list[PredictionResult], weights: list[float]
) -> list[list[float]]:
    """Element-wise weighted mean of N score matrices, normalised to sum 1."""
    arrays = [np.asarray(r.score_matrix, dtype=float) for r in results]
    fused = np.zeros_like(arrays[0])
    for w, a in zip(weights, arrays):
        fused = fused + w * a
    total = float(fused.sum())
    if total > 0:
        fused = fused / total
    return fused.tolist()

"""Abstract prediction-model interface + the `PredictionResult` data carrier.

Every Phase-2+ model implements `BasePredictionModel`. The Poisson baseline
is the only concrete implementation in Phase 2; gradient-boosted variants
land in later sub-phases. Subclasses are expected to be CPU-cheap to call
(`predict()` is exercised online by the FastAPI inference path).

`PredictionResult` is the unit of model output:
    * 1x2 probabilities (must sum to ~1)
    * Goal expectations λ for both sides
    * Full 10×10 score-probability matrix
    * Top-10 most-likely scorelines (sorted desc by prob)
    * Over/Under probabilities for the standard 1.5/2.5/3.5 lines
    * BTTS yes-probability
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class PredictionResult:
    """Model output for one match. Probabilities are floats in [0, 1].

    Attributes:
        prob_home_win: P(home win), the sum of P(i,j) for i > j.
        prob_draw: P(draw), the sum of P(i,i).
        prob_away_win: P(away win), the sum of P(i,j) for i < j.
        lambda_home: Expected home goals.
        lambda_away: Expected away goals.
        score_matrix: 10×10 matrix where ``[i][j] = P(home=i, away=j)``.
        top_scores: Top-10 most-likely scorelines, sorted desc by prob.
            Each entry is ``{"score": "i-j", "prob": float}``.
        over_under_probs: ``{"1.5": {"over": ..., "under": ...}, "2.5": ...}``.
        btts_prob: P(both teams to score).
    """

    prob_home_win: float
    prob_draw: float
    prob_away_win: float
    lambda_home: float
    lambda_away: float
    score_matrix: list[list[float]]
    top_scores: list[dict[str, Any]]
    over_under_probs: dict[str, dict[str, float]]
    btts_prob: float


class BasePredictionModel(ABC):
    """Abstract base class for every prediction model.

    Subclasses implement ``train`` / ``predict`` / ``get_model_version`` and
    use ``self.params`` (a plain dict) to serialize state. ``save`` and ``load``
    persist `params` as JSON next to the model-version stamp.
    """

    def __init__(self) -> None:
        self.params: dict[str, Any] = {}

    @abstractmethod
    def get_model_version(self) -> str:
        """Stable identifier persisted on every prediction (e.g. 'poisson_v1')."""

    @abstractmethod
    def train(self, features_df: pd.DataFrame) -> None:
        """Fit the model in-place from a feature DataFrame with label columns."""

    @abstractmethod
    def predict(self, features: dict[str, Any]) -> PredictionResult:
        """Produce a single-match `PredictionResult` from a feature dict."""

    def predict_batch(
        self, features_df: pd.DataFrame
    ) -> list[PredictionResult]:
        """Default loop. Override only when batch math beats N round-trips."""
        return [self.predict(_row_to_dict(row)) for _, row in features_df.iterrows()]

    # --- Persistence ---

    def save(self, path: str | Path) -> None:
        """Write the model params + version to disk as JSON."""
        import json

        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {"version": self.get_model_version(), "params": self.params}
        target.write_text(json.dumps(payload, sort_keys=True, indent=2))

    def load(self, path: str | Path) -> None:
        """Restore params from disk. Version mismatch raises `ValueError`."""
        import json

        target = Path(path)
        payload = json.loads(target.read_text())
        if payload.get("version") != self.get_model_version():
            raise ValueError(
                f"Model version mismatch: file is {payload.get('version')!r}, "
                f"this instance is {self.get_model_version()!r}"
            )
        self.params = payload.get("params") or {}


def _row_to_dict(row: pd.Series) -> dict[str, Any]:
    """Pandas Row → plain dict, coercing NaN to None for downstream safety."""
    out: dict[str, Any] = {}
    for key, value in row.items():
        if pd.isna(value):
            out[key] = None
        else:
            out[key] = value
    return out

"""Confidence scoring for predictions (0–100 + a 'low/medium/high' label).

The score is a weighted blend of four signals:

    * Probability concentration (40%): margin between top-1 and top-2 outcomes.
    * Data completeness (30%): non-None fraction of the feature dict.
    * Sample size (20%): based on `h2h_total_matches` (capped at 50).
    * Elo certainty (10%): magnitude of `elo_diff`, capped at ±500.

Sample-size note: the spec phrases it as "min(两队各自历史比赛数, 50)", but
team-history counts aren't directly exposed by the v1 feature set. We use
`h2h_total_matches` as a stand-in — it's the closest "how much history do we
have on this matchup?" signal we currently track. Phase 3's roster history
will give us per-team match counts and this proxy can be retired.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from src.ml.models.base import PredictionResult

# Component weights — must sum to 1.0.
W_CONCENTRATION: float = 0.40
W_DATA_COMPLETENESS: float = 0.30
W_SAMPLE_SIZE: float = 0.20
W_ELO_CERTAINTY: float = 0.10

# Normalisation knobs.
PROB_CONCENTRATION_DIFF_FOR_FULL_SCORE: float = 0.50  # diff=0.5 → 100
SAMPLE_SIZE_CAP: int = 50
ELO_DIFF_CAP: float = 500.0

# Score → level mapping.
LOW_THRESHOLD: int = 40
MEDIUM_THRESHOLD: int = 70


@dataclass(frozen=True)
class ConfidenceResult:
    """Confidence output: integer score plus categorical level + breakdown."""

    score: int
    level: str  # 'low' | 'medium' | 'high'
    breakdown: dict[str, float]


class ConfidenceCalculator:
    """Maps `(PredictionResult, features)` → integer score in [0, 100] + label."""

    def calculate(
        self,
        prediction: PredictionResult,
        features: dict[str, Any],
    ) -> ConfidenceResult:
        concentration = self._concentration_score(prediction)
        completeness = self._data_completeness_score(features)
        sample = self._sample_size_score(features)
        elo = self._elo_certainty_score(features)

        weighted = (
            W_CONCENTRATION * concentration
            + W_DATA_COMPLETENESS * completeness
            + W_SAMPLE_SIZE * sample
            + W_ELO_CERTAINTY * elo
        )
        score = max(0, min(100, round(weighted)))
        return ConfidenceResult(
            score=score,
            level=_score_to_level(score),
            breakdown={
                "concentration": concentration,
                "data_completeness": completeness,
                "sample_size": sample,
                "elo_certainty": elo,
            },
        )

    # --- Component scores (all in [0, 100]) ---

    @staticmethod
    def _concentration_score(prediction: PredictionResult) -> float:
        probs = sorted(
            (prediction.prob_home_win, prediction.prob_draw, prediction.prob_away_win),
            reverse=True,
        )
        diff = probs[0] - probs[1]
        return min(diff / PROB_CONCENTRATION_DIFF_FOR_FULL_SCORE, 1.0) * 100.0

    @staticmethod
    def _data_completeness_score(features: dict[str, Any]) -> float:
        if not features:
            return 0.0
        non_none = sum(1 for value in features.values() if value is not None)
        return (non_none / len(features)) * 100.0

    @staticmethod
    def _sample_size_score(features: dict[str, Any]) -> float:
        # See module docstring — H2H total stands in for per-team history.
        total = features.get("h2h_total_matches") or 0
        return min(total, SAMPLE_SIZE_CAP) / SAMPLE_SIZE_CAP * 100.0

    @staticmethod
    def _elo_certainty_score(features: dict[str, Any]) -> float:
        elo_diff = features.get("elo_diff") or 0.0
        return min(math.fabs(elo_diff), ELO_DIFF_CAP) / ELO_DIFF_CAP * 100.0


def _score_to_level(score: int) -> str:
    if score <= LOW_THRESHOLD:
        return "low"
    if score <= MEDIUM_THRESHOLD:
        return "medium"
    return "high"

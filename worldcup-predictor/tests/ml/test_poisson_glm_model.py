"""Unit tests for `PoissonGLMModel`."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.ml.models.poisson_glm import (
    FEATURE_NAMES,
    MODEL_VERSION,
    PoissonGLMModel,
)


def _toy_training_frame() -> pd.DataFrame:
    """Larger than the Poisson tests' frame because the GLM needs enough rows
    to produce non-degenerate coefficients after standardisation + L2.

    Goals are deliberately linked to elo_diff with a non-trivial coefficient
    so the regression has actual signal to fit — otherwise tests that check
    "elo_diff dominates outcome" would assert against pure noise."""
    rng = np.random.default_rng(0)
    n = 400
    elo = rng.normal(0, 200, n)
    # Stronger team scores ~more, weaker concedes ~more — emulates real data.
    home_lambda = np.clip(1.5 + elo / 200, 0.3, 5.0)
    away_lambda = np.clip(1.2 - elo / 200, 0.3, 5.0)
    return pd.DataFrame(
        {
            "elo_diff": elo,
            "home_xg_avg5": rng.gamma(2, 0.6, n),
            "away_xg_avg5": rng.gamma(2, 0.5, n),
            "home_xg_against_avg5": rng.gamma(2, 0.5, n),
            "away_xg_against_avg5": rng.gamma(2, 0.6, n),
            "home_goals_scored_avg5": rng.gamma(2, 0.6, n),
            "away_goals_scored_avg5": rng.gamma(2, 0.5, n),
            "home_goals_conceded_avg5": rng.gamma(2, 0.5, n),
            "away_goals_conceded_avg5": rng.gamma(2, 0.6, n),
            "home_win_rate_last5": rng.uniform(0, 1, n),
            "away_win_rate_last5": rng.uniform(0, 1, n),
            "home_unbeaten_streak": rng.integers(0, 6, n),
            "away_unbeaten_streak": rng.integers(0, 6, n),
            "label_home_score": rng.poisson(home_lambda),
            "label_away_score": rng.poisson(away_lambda),
        }
    )


def _balanced_features() -> dict[str, float]:
    return {
        "elo_diff": 0.0,
        "home_xg_avg5": 1.5, "away_xg_avg5": 1.5,
        "home_xg_against_avg5": 1.0, "away_xg_against_avg5": 1.0,
        "home_goals_scored_avg5": 1.5, "away_goals_scored_avg5": 1.5,
        "home_goals_conceded_avg5": 1.0, "away_goals_conceded_avg5": 1.0,
        "home_win_rate_last5": 0.5, "away_win_rate_last5": 0.5,
        "home_unbeaten_streak": 2, "away_unbeaten_streak": 2,
    }


def test_train_populates_eight_coefficients():
    m = PoissonGLMModel()
    m.train(_toy_training_frame())
    assert len(m.params["coef"]) == len(FEATURE_NAMES)
    assert m.params["feature_names"] == list(FEATURE_NAMES)
    assert m.params["intercept"] is not None
    # StandardScaler stats persist alongside so the predict path can rehydrate.
    assert len(m.params["scaler_mean"]) == len(FEATURE_NAMES)
    assert len(m.params["scaler_scale"]) == len(FEATURE_NAMES)


def test_predict_outcome_probs_sum_to_one():
    m = PoissonGLMModel()
    m.train(_toy_training_frame())
    pred = m.predict(_balanced_features())
    total = pred.prob_home_win + pred.prob_draw + pred.prob_away_win
    assert total == pytest.approx(1.0, abs=1e-6)


def test_elo_diff_dominates_outcome():
    """A large positive elo_diff should make the home team strongly favoured."""
    m = PoissonGLMModel()
    m.train(_toy_training_frame())
    feats_strong = {**_balanced_features(), "elo_diff": 400.0}
    feats_weak = {**_balanced_features(), "elo_diff": -400.0}
    strong = m.predict(feats_strong)
    weak = m.predict(feats_weak)
    # Home should be heavy favourite when elo gap is +400 and underdog at -400.
    assert strong.prob_home_win > weak.prob_home_win
    # On reversed gap, home win should drop AND away win should rise.
    assert strong.prob_away_win < weak.prob_away_win


def test_predict_lambdas_clamped_to_safe_range():
    """Even adversarial inputs (massive elo_diff) shouldn't produce λ=0 or λ→∞.

    The clip in :meth:`predict` keeps λ ∈ [0.05, 8.0] so the score-matrix
    builder doesn't overflow the truncation tail."""
    m = PoissonGLMModel()
    m.train(_toy_training_frame())
    feats = {**_balanced_features(), "elo_diff": 5000.0}  # absurd
    pred = m.predict(feats)
    assert 0.0 < pred.lambda_home < 10.0
    assert 0.0 < pred.lambda_away < 10.0


def test_save_load_roundtrip_preserves_predictions(tmp_path: Path):
    """Critical for MLflow Production loading: round-trip through JSON without
    pickling any sklearn estimator should yield identical λ predictions."""
    m1 = PoissonGLMModel()
    m1.train(_toy_training_frame())
    pred_before = m1.predict(_balanced_features())

    save_path = tmp_path / "model.json"
    m1.save(save_path)

    # Sanity: the JSON file is plain text and contains the coefficients.
    payload = json.loads(save_path.read_text())
    assert payload["version"] == MODEL_VERSION
    assert "coef" in payload["params"]

    m2 = PoissonGLMModel()
    m2.load(save_path)
    pred_after = m2.predict(_balanced_features())

    assert pred_after.lambda_home == pytest.approx(pred_before.lambda_home, abs=1e-6)
    assert pred_after.lambda_away == pytest.approx(pred_before.lambda_away, abs=1e-6)
    assert pred_after.prob_home_win == pytest.approx(pred_before.prob_home_win, abs=1e-6)


def test_untrained_model_raises():
    m = PoissonGLMModel()
    with pytest.raises(RuntimeError, match="untrained"):
        m.predict(_balanced_features())


def test_missing_features_default_to_zero_safely():
    """Inference shouldn't crash when an upstream feature dict has gaps —
    `_safe_float` coerces None / NaN / missing keys to 0.0 before scaling."""
    m = PoissonGLMModel()
    m.train(_toy_training_frame())
    sparse = {"elo_diff": 50.0}  # almost everything missing
    pred = m.predict(sparse)
    assert 0.0 < pred.lambda_home < 10.0
    assert 0.0 < pred.lambda_away < 10.0

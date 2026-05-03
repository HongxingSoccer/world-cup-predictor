"""Unit tests for `ConfidenceCalculator`."""
from __future__ import annotations

from src.ml.models.base import PredictionResult
from src.ml.models.confidence import ConfidenceCalculator


def _make_prediction(home: float, draw: float, away: float) -> PredictionResult:
    """Tiny helper — only the 1x2 probs matter for confidence math."""
    return PredictionResult(
        prob_home_win=home,
        prob_draw=draw,
        prob_away_win=away,
        lambda_home=1.5,
        lambda_away=1.0,
        score_matrix=[[0.0] * 10 for _ in range(10)],
        top_scores=[],
        over_under_probs={"2.5": {"over": 0.5, "under": 0.5}},
        btts_prob=0.5,
    )


def test_all_factors_max_yields_score_at_or_near_100():
    pred = _make_prediction(0.85, 0.10, 0.05)  # diff = 0.75 → caps at 100
    features = {
        "elo_diff": 600.0,            # caps at 500 → 100
        "h2h_total_matches": 60,      # caps at 50 → 100
        "feature_a": 1.0,             # all non-None → completeness 100
    }
    out = ConfidenceCalculator().calculate(pred, features)
    assert out.score == 100
    assert out.level == "high"


def test_all_factors_zero_yields_zero():
    # Equal 1x2 → diff = 0 → concentration = 0
    pred = _make_prediction(1 / 3, 1 / 3, 1 / 3)
    # All features None → completeness 0. Missing elo_diff / h2h_total_matches
    # fall back to 0 inside the calculator (both via `.get(...) or 0`).
    features = {"feature_a": None, "feature_b": None}
    out = ConfidenceCalculator().calculate(pred, features)
    assert out.score == 0
    assert out.level == "low"


def test_concentration_factor_zero_when_top_two_close():
    pred = _make_prediction(0.34, 0.33, 0.33)  # diff = 0.01 → ~2
    features = {"elo_diff": 0.0, "h2h_total_matches": 0, "k": None}
    out = ConfidenceCalculator().calculate(pred, features)
    assert out.breakdown["concentration"] < 5.0


def test_concentration_factor_full_when_diff_half():
    pred = _make_prediction(0.65, 0.15, 0.20)  # diff = 0.45 → 90
    features = {"elo_diff": 0.0, "h2h_total_matches": 0, "k": None}
    out = ConfidenceCalculator().calculate(pred, features)
    assert out.breakdown["concentration"] >= 90.0


def test_score_to_level_thresholds():
    pred = _make_prediction(0.50, 0.30, 0.20)  # mid-range
    features = {"elo_diff": 100.0, "h2h_total_matches": 5, "k": 1.0}
    out = ConfidenceCalculator().calculate(pred, features)
    assert 0 <= out.score <= 100
    assert out.level in {"low", "medium", "high"}

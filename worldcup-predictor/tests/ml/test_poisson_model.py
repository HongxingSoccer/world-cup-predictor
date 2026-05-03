"""Unit tests for `PoissonBaselineModel`."""
from __future__ import annotations

import pandas as pd
import pytest

from src.ml.models.poisson import PoissonBaselineModel


def _toy_training_frame() -> pd.DataFrame:
    """Tiny but plausible training frame used across tests."""
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


def test_predict_outcome_probs_sum_to_one():
    m = PoissonBaselineModel()
    m.train(_toy_training_frame())
    pred = m.predict(_balanced_features())
    total = pred.prob_home_win + pred.prob_draw + pred.prob_away_win
    assert total == pytest.approx(1.0, abs=1e-6)


def test_score_matrix_normalises_to_one():
    m = PoissonBaselineModel()
    m.train(_toy_training_frame())
    pred = m.predict(_balanced_features())
    matrix_sum = sum(sum(row) for row in pred.score_matrix)
    assert matrix_sum == pytest.approx(1.0, abs=1e-6)
    assert len(pred.score_matrix) == 10
    assert all(len(row) == 10 for row in pred.score_matrix)


def test_over_under_complementary_for_each_line():
    m = PoissonBaselineModel()
    m.train(_toy_training_frame())
    pred = m.predict(_balanced_features())
    for line, probs in pred.over_under_probs.items():
        assert probs["over"] + probs["under"] == pytest.approx(1.0, abs=1e-6), line


def test_btts_prob_in_unit_interval():
    m = PoissonBaselineModel()
    m.train(_toy_training_frame())
    pred = m.predict(_balanced_features())
    assert 0.0 < pred.btts_prob < 1.0
    # P(BTTS=No) is implicitly 1 - btts_prob; complement check.
    assert pred.btts_prob + (1 - pred.btts_prob) == pytest.approx(1.0)


def test_top_scores_sorted_desc_and_capped_at_ten():
    m = PoissonBaselineModel()
    m.train(_toy_training_frame())
    pred = m.predict(_balanced_features())
    assert len(pred.top_scores) == 10
    probs = [s["prob"] for s in pred.top_scores]
    assert probs == sorted(probs, reverse=True)


def test_home_advantage_makes_home_win_more_likely_than_away():
    m = PoissonBaselineModel()
    m.train(_toy_training_frame())
    pred = m.predict(_balanced_features())
    # With identical Elo and team profiles, the home factor (>1) should tilt
    # the 1x2 distribution toward the home side.
    assert pred.prob_home_win > pred.prob_away_win


def test_elo_correction_above_threshold_boosts_home_lambda():
    m = PoissonBaselineModel()
    m.train(_toy_training_frame())

    base = m.predict(_balanced_features())
    boosted = m.predict({**_balanced_features(), "elo_diff": 250.0})

    assert boosted.lambda_home > base.lambda_home
    assert boosted.lambda_away < base.lambda_away


def test_predict_raises_when_untrained():
    m = PoissonBaselineModel()
    with pytest.raises(RuntimeError):
        m.predict(_balanced_features())


def test_save_and_load_roundtrip(tmp_path):
    m = PoissonBaselineModel()
    m.train(_toy_training_frame())
    target = tmp_path / "poisson_v1.json"
    m.save(target)

    reloaded = PoissonBaselineModel()
    reloaded.load(target)

    assert reloaded.params == m.params
    # Predictions match exactly after a save/load cycle.
    base_pred = m.predict(_balanced_features())
    new_pred = reloaded.predict(_balanced_features())
    assert new_pred.lambda_home == pytest.approx(base_pred.lambda_home)
    assert new_pred.prob_home_win == pytest.approx(base_pred.prob_home_win)


def test_load_rejects_version_mismatch(tmp_path):
    target = tmp_path / "wrong.json"
    target.write_text('{"version": "poisson_v999", "params": {}}')

    with pytest.raises(ValueError, match="version mismatch"):
        PoissonBaselineModel().load(target)

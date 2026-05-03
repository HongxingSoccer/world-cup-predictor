"""Unit tests for `PredictionService` (publish=False path) + content-hash determinism.

The publish=True path requires the `predictions` JSONB tables and the
PostgreSQL immutability trigger. Those are exercised separately in
`tests/test_predictions_immutability_pg.py`, which is gated on a real Postgres.
"""
from __future__ import annotations

import pandas as pd
import pytest

from src.ml.features.pipeline import FeaturePipeline
from src.ml.models.confidence import ConfidenceCalculator
from src.ml.models.poisson import PoissonBaselineModel
from src.ml.odds.analyzer import OddsAnalyzer
from src.ml.prediction_service import PredictionService, compute_content_hash


@pytest.fixture()
def trained_model() -> PoissonBaselineModel:
    df = pd.DataFrame(
        {
            "home_xg_avg5": [1.5, 1.0, 2.0, 1.8] * 5,
            "away_xg_avg5": [1.0, 1.2, 0.8, 1.5] * 5,
            "home_goals_scored_avg5": [1.5, 1.0, 2.0, 1.5] * 5,
            "away_goals_scored_avg5": [1.0, 1.2, 0.8, 1.5] * 5,
            "home_xg_against_avg5": [1.0, 1.5, 0.5, 1.2] * 5,
            "away_xg_against_avg5": [1.5, 1.0, 1.5, 1.5] * 5,
            "home_goals_conceded_avg5": [1.0, 1.5, 0.5, 1.2] * 5,
            "away_goals_conceded_avg5": [1.5, 1.0, 1.5, 1.5] * 5,
            "label_home_score": [2, 1, 3, 2] * 5,
            "label_away_score": [1, 1, 0, 2] * 5,
        }
    )
    m = PoissonBaselineModel()
    m.train(df)
    return m


def _service(db_session, model: PoissonBaselineModel) -> PredictionService:
    return PredictionService(
        db_session=db_session,
        model=model,
        feature_pipeline=FeaturePipeline(db_session),
        odds_analyzer=OddsAnalyzer(db_session),
        confidence_calculator=ConfidenceCalculator(),
    )


def test_generate_prediction_unpublished_returns_full_result(
    db_session, make_match, utc, trained_model
):
    target = make_match(utc(2026, 5, 1, 18))
    db_session.flush()

    result = _service(db_session, trained_model).generate_prediction(target.id)

    assert result.match_id == target.id
    assert result.model_version == "poisson_v1"
    assert result.feature_version == "v1"
    # Probabilities form a valid distribution.
    p = result.prediction
    assert p.prob_home_win + p.prob_draw + p.prob_away_win == pytest.approx(1.0, abs=1e-6)
    # No persistence yet → no prediction_id and no hash.
    assert result.prediction_id is None
    assert result.content_hash is None


def test_generate_prediction_rejects_cancelled_match(
    db_session, make_match, utc, trained_model
):
    target = make_match(utc(2026, 5, 1, 18), status="cancelled")
    db_session.flush()

    with pytest.raises(ValueError, match="cancelled"):
        _service(db_session, trained_model).generate_prediction(target.id)


def test_generate_prediction_unknown_match_raises(db_session, trained_model):
    with pytest.raises(ValueError, match="not found"):
        _service(db_session, trained_model).generate_prediction(99999)


# --- content_hash semantics ---------------------------------------------


def test_content_hash_deterministic_for_identical_input(
    db_session, make_match, utc, trained_model
):
    target = make_match(utc(2026, 5, 1, 18))
    db_session.flush()

    result_a = _service(db_session, trained_model).generate_prediction(target.id)
    result_b = _service(db_session, trained_model).generate_prediction(target.id)

    h_a = compute_content_hash(result_a.prediction, result_a.features_snapshot, result_a.confidence)
    h_b = compute_content_hash(result_b.prediction, result_b.features_snapshot, result_b.confidence)
    assert h_a == h_b


def test_content_hash_changes_when_any_feature_changes(
    db_session, make_match, utc, trained_model
):
    target = make_match(utc(2026, 5, 1, 18))
    db_session.flush()

    result = _service(db_session, trained_model).generate_prediction(target.id)
    base_hash = compute_content_hash(
        result.prediction, result.features_snapshot, result.confidence
    )

    # Alter a single feature value.
    tampered_features = {**result.features_snapshot, "home_xg_avg5": 99.0}
    tampered_hash = compute_content_hash(
        result.prediction, tampered_features, result.confidence
    )

    assert base_hash != tampered_hash
    assert len(base_hash) == 64  # SHA-256 hex digest length

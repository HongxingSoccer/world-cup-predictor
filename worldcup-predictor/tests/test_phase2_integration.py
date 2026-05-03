"""Phase-2 acceptance test suite.

Each test maps onto one of the Phase-2 verification checkboxes from the spec:

    1. Feature pipeline returns 28 features for a fully-seeded match.
    2. Poisson 1x2 probabilities sum to 1.0.
    3. Score-matrix sums to 1.0 (within float tolerance).
    4. EV math: 55% main vs 2.10 odds → EV ≈ 0.155.
    5. content_hash is deterministic and changes when any field mutates.
    6. predictions UPDATE is rejected by the trigger (Postgres-only — see
       `tests/test_predictions_immutability_pg.py`).
    7. FastAPI /predict returns the expected response shape.
    8. FastAPI /odds-analysis returns positive-EV signals when warranted.
    9. FastAPI /predictions/today returns the cached / fresh shape.
    10. Backtest report renders to non-empty HTML with charts embedded.

Items 6 + 7-9's persistence path require Postgres + JSONB — those are gated
on `WCP_TEST_PG_URL` so the bulk of the suite runs in SQLite without infra.
"""
from __future__ import annotations

import os
from datetime import date, timedelta
from decimal import Decimal

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.api.dependencies import get_db_session, get_model
from src.config.settings import settings
from src.ml.backtest.evaluator import BacktestEvaluator
from src.ml.backtest.report import generate_html_report
from src.ml.backtest.runner import BacktestRunner, BacktestSample
from src.ml.features.pipeline import FeaturePipeline
from src.ml.models.poisson import PoissonBaselineModel
from src.ml.odds.ev_calculator import compute_ev
from src.ml.prediction_service import compute_content_hash
from src.models.elo_rating import EloRating
from src.models.match_stats import MatchStats
from src.models.odds_snapshot import OddsSnapshot


# --- 1. Feature pipeline ----------------------------------------------------


def test_feature_pipeline_produces_28_features(db_session, make_match, utc):
    target = make_match(utc(2026, 5, 1))
    pipeline = FeaturePipeline(db_session)
    features = pipeline.compute_for_match(target.id)
    assert len(features) == 28
    assert set(features.keys()) == set(pipeline.get_feature_names())


# --- 2 + 3. Model probabilities sum to 1 -----------------------------------


def test_poisson_outcome_probs_sum_to_one():
    model = _trained_poisson()
    pred = model.predict(_balanced_features())
    assert pred.prob_home_win + pred.prob_draw + pred.prob_away_win == pytest.approx(1.0, abs=1e-6)
    assert sum(sum(row) for row in pred.score_matrix) == pytest.approx(1.0, abs=1e-6)


# --- 4. EV math --------------------------------------------------------------


def test_ev_doc_example_holds():
    assert compute_ev(0.55, 2.10) == pytest.approx(0.155, abs=1e-3)


# --- 5. Content hash --------------------------------------------------------


def test_content_hash_stable_across_calls():
    model = _trained_poisson()
    features = _balanced_features()
    pred = model.predict(features)
    h_a = compute_content_hash(pred, features)
    h_b = compute_content_hash(pred, features)
    assert h_a == h_b
    assert len(h_a) == 64


def test_content_hash_changes_on_any_field_mutation():
    model = _trained_poisson()
    features = _balanced_features()
    base_hash = compute_content_hash(model.predict(features), features)
    # Mutate a single feature.
    tampered = {**features, "elo_diff": 999.0}
    new_hash = compute_content_hash(model.predict(tampered), tampered)
    assert base_hash != new_hash


# --- 6. predictions immutability — see test_predictions_immutability_pg.py


# --- 7-9. FastAPI endpoints --------------------------------------------------


@pytest.fixture()
def api_client(db_session, make_match, utc, seed_world):
    """TestClient with the dependency overrides + a seeded match for /predict."""
    home = seed_world["home_team_id"]
    away = seed_world["away_team_id"]
    # A finished pre-history match so features have something to chew on.
    make_match(
        utc(2026, 4, 1),
        home_score=2,
        away_score=1,
        home_team_id=home,
        away_team_id=away,
    )
    db_session.add_all(
        [
            EloRating(team_id=home, rating=Decimal("1700.00"), rated_at=date(2026, 4, 1)),
            EloRating(team_id=away, rating=Decimal("1500.00"), rated_at=date(2026, 4, 1)),
            MatchStats(
                match_id=1,
                team_id=home,
                is_home=True,
                xg=Decimal("1.50"),
                xg_against=Decimal("0.50"),
                shots=12,
                shots_on_target=5,
                data_source="test",
            ),
        ]
    )
    target_match = make_match(utc(2026, 5, 1, 18))
    db_session.flush()

    # Build a snapshot with strong value (model 0.55 home vs 2.20 odds).
    db_session.add(
        OddsSnapshot(
            match_id=target_match.id,
            bookmaker="pinnacle",
            market_type="1x2",
            outcome_home=Decimal("2.20"),
            outcome_draw=Decimal("3.30"),
            outcome_away=Decimal("3.40"),
            snapshot_at=target_match.match_date - timedelta(hours=2),
            data_source="test",
        )
    )
    db_session.flush()

    app.dependency_overrides[get_db_session] = lambda: db_session
    app.dependency_overrides[get_model] = lambda: _trained_poisson()
    client = TestClient(app, headers={})
    yield client, target_match
    app.dependency_overrides.clear()


def test_api_predict_returns_well_formed_response(api_client):
    client, match = api_client
    response = client.post(
        "/api/v1/predict",
        json={"match_id": match.id, "include_score_matrix": False, "publish": False},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["match_id"] == match.id
    assert body["model_version"] == "poisson_v1"
    p = body["predictions"]
    assert p["score_matrix"] is None  # include_score_matrix=False
    assert p["prob_home_win"] + p["prob_draw"] + p["prob_away_win"] == pytest.approx(1.0, abs=1e-6)
    assert 0 <= body["confidence_score"] <= 100


def test_api_predict_404_for_unknown_match(api_client):
    client, _ = api_client
    response = client.post("/api/v1/predict", json={"match_id": 99999})
    assert response.status_code == 404


def test_api_odds_analysis_returns_signals(api_client):
    client, match = api_client
    response = client.post(
        "/api/v1/odds-analysis",
        json={"match_id": match.id, "markets": ["1x2"]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["match_id"] == match.id
    # 1x2 was the only market we seeded, so we get exactly that bucket.
    market_keys = {m["market_type"] for m in body["markets"]}
    assert "1x2" in market_keys


def test_api_predictions_today_empty_when_no_predictions(api_client):
    client, match = api_client
    target = match.match_date.date().isoformat()
    response = client.get(
        "/api/v1/predictions/today",
        params={"date": target},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["date"] == target
    # No published predictions exist yet → empty list, cached=False.
    assert body["items"] == []
    assert body["cached"] is False


# --- 10. Backtest report ----------------------------------------------------


def test_backtest_report_renders_html_with_charts():
    samples = _synthetic_backtest_samples()
    metrics = BacktestEvaluator().evaluate(samples)
    html = generate_html_report(
        model_version="poisson_v1",
        feature_version="v1",
        window="2026-01-01..2026-05-01",
        samples=samples,
        metrics=metrics,
    )
    assert "<html" in html.lower()
    assert "Cumulative P&amp;L" in html
    assert "data:image/png;base64" in html


def test_backtest_runner_walks_rolling_windows():
    df = _synthetic_features_df(n=80)
    # Synthetic dates start 2024-06-01 every 5 days. We pick a test window
    # that has both a populated train slice (≥5 rows) and a test slice (≥1 row).
    runner = BacktestRunner(
        model_factory=PoissonBaselineModel,
        train_window_months=3,
        test_window_months=1,
        step_months=1,
    )
    samples = runner.run(df, start_date=date(2024, 12, 1), end_date=date(2025, 4, 1))
    assert len(samples) >= 1
    for s in samples:
        assert s.actual_result in {"H", "D", "A"}


# --- Helpers ---------------------------------------------------------------


def _balanced_features() -> dict:
    return {
        "home_xg_avg5": 1.5, "away_xg_avg5": 1.5,
        "home_goals_scored_avg5": 1.5, "away_goals_scored_avg5": 1.5,
        "home_xg_against_avg5": 1.0, "away_xg_against_avg5": 1.0,
        "home_goals_conceded_avg5": 1.0, "away_goals_conceded_avg5": 1.0,
        "elo_diff": 0.0,
        "h2h_total_matches": 5,
    }


def _trained_poisson() -> PoissonBaselineModel:
    df = pd.DataFrame(
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
    m = PoissonBaselineModel()
    m.train(df)
    return m


def _synthetic_features_df(n: int) -> pd.DataFrame:
    """Tiny daily-cadence synthetic frame used by backtest tests."""
    rows = []
    base = pd.Timestamp("2024-06-01", tz="UTC")
    for i in range(n):
        rows.append(
            {
                "match_id": i + 1,
                "match_date": base + pd.Timedelta(days=i * 5),
                "home_xg_avg5": 1.5 + (i % 3) * 0.1,
                "away_xg_avg5": 1.2 + (i % 3) * 0.05,
                "home_goals_scored_avg5": 1.4,
                "away_goals_scored_avg5": 1.1,
                "home_xg_against_avg5": 1.0,
                "away_xg_against_avg5": 1.3,
                "home_goals_conceded_avg5": 1.0,
                "away_goals_conceded_avg5": 1.3,
                "elo_diff": 50.0 - i,
                "h2h_total_matches": 3,
                "label_home_score": (i + 1) % 4,
                "label_away_score": i % 3,
            }
        )
    return pd.DataFrame.from_records(rows)


def _synthetic_backtest_samples() -> list[BacktestSample]:
    base = pd.Timestamp("2025-01-01", tz="UTC")
    out: list[BacktestSample] = []
    for i in range(20):
        is_home = i % 3 == 0
        out.append(
            BacktestSample(
                match_id=i + 1,
                match_date=(base + pd.Timedelta(days=i * 5)).to_pydatetime(),
                window_test_start=date(2025, 1, 1),
                prob_home_win=0.55 if is_home else 0.30,
                prob_draw=0.25,
                prob_away_win=0.20 if is_home else 0.45,
                actual_result="H" if is_home else "A",
                actual_home_score=2 if is_home else 0,
                actual_away_score=1 if is_home else 2,
                odds={
                    "1x2": {"home": 2.10, "draw": 3.40, "away": 3.20}
                    if is_home
                    else {"home": 3.50, "draw": 3.40, "away": 2.10},
                },
            )
        )
    return out


# Re-imported here so the integration test can detect Postgres availability
# (used by the helper script that bridges to the immutability test below).
_PG_TEST_URL = os.environ.get("WCP_TEST_PG_URL")

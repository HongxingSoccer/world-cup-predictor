"""Integration tests for `FeaturePipeline`.

These exercise the orchestrator on top of the SQLite world, but skip the
JSONB-backed persistence (`save_to_db` / `export_to_parquet`) — those need
PostgreSQL and are covered by Phase-2 integration tests, not unit tests.
"""
from __future__ import annotations

import pandas as pd

from src.ml.features.pipeline import FeaturePipeline


def test_get_feature_names_returns_28_unique_names(db_session):
    names = FeaturePipeline(db_session).get_feature_names()
    assert len(names) == 28
    assert len(set(names)) == 28


def test_compute_for_match_returns_full_vector(db_session, make_match, utc):
    match = make_match(utc(2026, 5, 1))
    pipeline = FeaturePipeline(db_session)

    features = pipeline.compute_for_match(match.id)

    assert set(features.keys()) == set(pipeline.get_feature_names())


def test_compute_batch_returns_dataframe_keyed_on_match_id(
    db_session, make_match, utc
):
    match_a = make_match(utc(2026, 5, 1))
    match_b = make_match(utc(2026, 5, 2))

    df = FeaturePipeline(db_session).compute_batch([match_a.id, match_b.id])

    assert isinstance(df, pd.DataFrame)
    assert df.index.name == "match_id"
    assert list(df.index) == [match_a.id, match_b.id]
    assert df.shape == (2, 28)


def test_compute_for_match_uses_match_kickoff_as_default_cutoff(
    db_session, make_match, utc, seed_world
):
    """Without explicit cutoff, the pipeline must use the match's kickoff time
    so a match never sees its own row."""
    home = seed_world["home_team_id"]
    away = seed_world["away_team_id"]
    target = make_match(utc(2026, 5, 1), home_score=2, away_score=1,
                         home_team_id=home, away_team_id=away)
    db_session.flush()

    features = FeaturePipeline(db_session).compute_for_match(target.id)
    # h2h must show zero past meetings — the only meeting IS this match.
    assert features["h2h_total_matches"] == 0

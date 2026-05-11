"""Postgres-only test for the `predictions` immutability trigger.

Skipped unless the env var ``WCP_TEST_PG_URL`` points to a reachable
PostgreSQL whose schema has Phase-2 migrations applied. CI / local dev
runs the rest of the suite against SQLite, but the trigger itself only
exists on Postgres so this test must talk to the real thing.

To enable locally:
    docker run -d --rm --name wcp-it-pg -e POSTGRES_USER=wcp \
        -e POSTGRES_PASSWORD=wcp -e POSTGRES_DB=wcp \
        -p 55432:5432 postgres:15-alpine
    DATABASE_URL=postgresql+psycopg2://wcp:wcp@localhost:55432/wcp \
        alembic upgrade head
    WCP_TEST_PG_URL=postgresql+psycopg2://wcp:wcp@localhost:55432/wcp pytest \
        tests/test_predictions_immutability_pg.py
"""
from __future__ import annotations

import os
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

PG_URL = os.environ.get("WCP_TEST_PG_URL")
pytestmark = pytest.mark.skipif(
    not PG_URL,
    reason="WCP_TEST_PG_URL is not set — requires a real PostgreSQL with Phase-2 schema applied.",
)


def _seed_prediction(session: Session) -> int:
    """Insert minimal supporting rows + one prediction. Returns prediction id."""
    session.execute(
        text("INSERT INTO competitions (name, competition_type) VALUES ('Imm', 'national')")
    )
    session.execute(text("INSERT INTO seasons (competition_id, year) VALUES (1, 2026)"))
    session.execute(text("INSERT INTO teams (name, team_type) VALUES ('A', 'national')"))
    session.execute(text("INSERT INTO teams (name, team_type) VALUES ('B', 'national')"))
    session.execute(
        text(
            "INSERT INTO matches (season_id, home_team_id, away_team_id, "
            "match_date, status) VALUES (1, 1, 2, NOW(), 'finished')"
        )
    )
    pred_row = session.execute(
        text(
            """
            INSERT INTO predictions (
                match_id, model_version, feature_version,
                prob_home_win, prob_draw, prob_away_win,
                lambda_home, lambda_away,
                score_matrix, top_scores, over_under_probs, btts_prob,
                confidence_score, confidence_level,
                features_snapshot, content_hash, published_at
            ) VALUES (
                1, 'poisson_v1', 'v1',
                0.50, 0.25, 0.25, 1.5, 1.0,
                '[[0.1]]'::jsonb, '[]'::jsonb, '{}'::jsonb, 0.5,
                72, 'high',
                '{}'::jsonb, :hash, :ts
            ) RETURNING id
            """
        ),
        {
            "hash": "a" * 64,
            "ts": datetime.now(UTC),
        },
    ).first()
    session.commit()
    return int(pred_row[0])


@pytest.fixture()
def pg_session():  # type: ignore[no-untyped-def]
    engine = create_engine(PG_URL or "", future=True)
    with engine.begin() as conn:
        # Per-test sandbox: clean slate for the supporting tables.
        conn.execute(
            text(
                "TRUNCATE odds_analysis, predictions, match_features, matches, "
                "seasons, competitions, teams RESTART IDENTITY CASCADE"
            )
        )
    with Session(engine) as session:
        yield session
    engine.dispose()


def test_update_predictions_is_rejected(pg_session: Session) -> None:
    pred_id = _seed_prediction(pg_session)
    with pytest.raises(Exception, match="immutable"):
        pg_session.execute(
            text("UPDATE predictions SET prob_home_win = 0.99 WHERE id = :id"),
            {"id": pred_id},
        )
        pg_session.commit()


def test_delete_predictions_is_rejected(pg_session: Session) -> None:
    pred_id = _seed_prediction(pg_session)
    with pytest.raises(Exception, match="immutable"):
        pg_session.execute(
            text("DELETE FROM predictions WHERE id = :id"), {"id": pred_id}
        )
        pg_session.commit()


def test_insert_into_predictions_is_allowed(pg_session: Session) -> None:
    pred_id = _seed_prediction(pg_session)
    assert pred_id > 0
    # A second insert with a different model_version should also succeed
    # (UNIQUE is on (match_id, model_version)).
    pg_session.execute(
        text(
            """
            INSERT INTO predictions (
                match_id, model_version, feature_version,
                prob_home_win, prob_draw, prob_away_win,
                lambda_home, lambda_away,
                score_matrix, top_scores, over_under_probs, btts_prob,
                confidence_score, confidence_level,
                features_snapshot, content_hash, published_at
            ) VALUES (
                1, 'poisson_v2', 'v1',
                0.40, 0.30, 0.30, 1.2, 1.2,
                '[[0.05]]'::jsonb, '[]'::jsonb, '{}'::jsonb, 0.4,
                65, 'medium',
                '{}'::jsonb, :hash, :ts
            )
            """
        ),
        {
            "hash": "b" * 64,
            "ts": datetime.now(UTC),
        },
    )
    pg_session.commit()

"""Top-level pytest fixtures shared across the whole test suite.

Two groups of fixtures live here:

    1. `_instant_rate_limiter` (autouse) — strips the 0.5–2 s jitter from
       `RateLimiter.acquire()` so adapter tests don't burn wall-clock time.

    2. SQLite-backed DB fixtures (`db_engine` / `db_session` / `seed_world` /
       `make_match` / `utc`). Used by feature-calculator and model tests.
       Postgres-only types (JSONB) are auto-converted via SQLAlchemy compile
       hooks below so most ORM tables work in-memory; tables that genuinely
       need Postgres (predictions / match_features / odds_analysis with their
       JSONB payload contracts) are intentionally excluded from create_all.

Tests that absolutely need a real Postgres should use the `WCP_TEST_PG_URL`
env var pattern (see `tests/test_predictions_immutability_pg.py`).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterator

import pytest
from sqlalchemy import BigInteger, create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import src.models  # noqa: F401 — register every ORM table on Base.metadata
from src.models.base import Base
from src.models.competition import Competition
from src.models.match import Match
from src.models.season import Season
from src.models.team import Team
from src.utils import rate_limiter as rl


# --- SQLite type compatibility shims (test-only) ---


@compiles(BigInteger, "sqlite")
def _bigint_to_integer_on_sqlite(type_, compiler, **kw):  # type: ignore[no-untyped-def]
    """BigInteger → INTEGER on SQLite so PKs become rowid aliases (auto-increment)."""
    return "INTEGER"


@compiles(JSONB, "sqlite")
def _jsonb_to_json_on_sqlite(type_, compiler, **kw):  # type: ignore[no-untyped-def]
    """JSONB → JSON on SQLite. SQLAlchemy will still serialize via json.dumps."""
    return "JSON"


# Tables that round-trip safely under SQLite. JSONB columns are mapped to
# JSON via the compile hook above, so all 18 schema tables work — but the
# `predictions` immutability trigger is Postgres-only and has its own gated
# test in `test_predictions_immutability_pg.py`.
_PORTABLE_TABLE_NAMES: frozenset[str] = frozenset(
    {
        # Phase 1 (data foundation)
        "competitions", "seasons", "teams", "players", "matches",
        "match_stats", "match_lineups", "player_stats",
        "player_valuations", "injuries", "elo_ratings",
        "team_name_aliases", "h2h_records", "odds_snapshots",
        "data_source_logs",
        # Phase 2 (ML output)
        "match_features", "predictions", "odds_analysis",
        # Phase 3 (business + social + settlement)
        "users", "user_oauth", "payments", "subscriptions",
        "prediction_results", "track_record_stats",
        "share_links", "share_cards", "user_favorites",
        # Phase 4 (ML reports + push)
        "analysis_reports", "simulation_results",
        "push_notifications", "user_push_settings",
    }
)


# --- Autouse: instant rate limiter ---


@pytest.fixture(autouse=True)
def _instant_rate_limiter(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make every `RateLimiter.acquire()` resolve immediately."""

    async def _instant(self: rl.RateLimiter, *, jitter: bool = True) -> None:
        return None

    monkeypatch.setattr(rl.RateLimiter, "acquire", _instant)


# --- DB fixtures ---


@pytest.fixture()
def db_engine():  # type: ignore[no-untyped-def]
    # `check_same_thread=False` + StaticPool let FastAPI's TestClient (which
    # invokes endpoints on a worker thread) share the in-memory database
    # with the test thread that seeded it.
    engine = create_engine(
        "sqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    portable_tables = [
        t for t in Base.metadata.sorted_tables if t.name in _PORTABLE_TABLE_NAMES
    ]
    Base.metadata.create_all(engine, tables=portable_tables)
    yield engine
    engine.dispose()


@pytest.fixture()
def db_session(db_engine) -> Iterator[Session]:  # type: ignore[no-untyped-def]
    Session_ = sessionmaker(bind=db_engine, autocommit=False, autoflush=False, future=True)
    session = Session_()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture()
def seed_world(db_session: Session) -> dict[str, int]:
    """Insert {competition, season, two national teams}. Returns lookup ids."""
    comp = Competition(name="Test Cup", competition_type="national")
    db_session.add(comp)
    db_session.flush()

    season = Season(competition_id=comp.id, year=2026)
    db_session.add(season)
    db_session.flush()

    home = Team(name="Alpha", team_type="national")
    away = Team(name="Beta", team_type="national")
    db_session.add_all([home, away])
    db_session.flush()

    return {
        "competition_id": comp.id,
        "season_id": season.id,
        "home_team_id": home.id,
        "away_team_id": away.id,
    }


@pytest.fixture()
def make_match(db_session: Session, seed_world: dict[str, int]):  # type: ignore[no-untyped-def]
    """Factory: insert a finished match with the given scores at `match_date`."""

    def _make(
        match_date: datetime,
        home_score: int | None = None,
        away_score: int | None = None,
        *,
        status: str = "finished",
        home_team_id: int | None = None,
        away_team_id: int | None = None,
        season_id: int | None = None,
    ) -> Match:
        match = Match(
            season_id=season_id or seed_world["season_id"],
            home_team_id=home_team_id or seed_world["home_team_id"],
            away_team_id=away_team_id or seed_world["away_team_id"],
            match_date=match_date,
            status=status,
            home_score=home_score,
            away_score=away_score,
        )
        db_session.add(match)
        db_session.flush()
        return match

    return _make


@pytest.fixture()
def utc():  # type: ignore[no-untyped-def]
    """Tiny shim so tests don't repeat `tzinfo=timezone.utc`."""

    def _utc(year: int, month: int, day: int, hour: int = 12) -> datetime:
        return datetime(year, month, day, hour, tzinfo=timezone.utc)

    return _utc

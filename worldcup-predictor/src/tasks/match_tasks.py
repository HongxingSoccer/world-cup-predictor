"""Celery tasks for fixture / score ingestion.

Three task families:

- `sync_matches_daily` — periodic, runs once per day at 06:00 UTC. Iterates
  every entry in `settings.ACTIVE_COMPETITIONS` and pulls the season's
  fixtures from API-Football.
- `sync_matches_live(match_id)` — on-demand, refreshes one in-progress match.
- `dispatch_dynamic_jobs` — periodic scanner that fans out the per-match work
  the Phase-1 spec calls "dynamic" (live scores, post-match stats, pre-kickoff
  odds) so we don't need real per-match cron entries.

All tasks return a small dict so Flower / the audit log can see what happened.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import select

from src.adapters.api_football import ApiFootballAdapter
from src.config.celery_config import (
    DEFAULT_MAX_RETRIES,
    DEFAULT_RETRY_BACKOFF,
    DEFAULT_RETRY_BACKOFF_MAX,
    app,
)
from src.config.settings import settings
from src.events.producer import build_producer
from src.models.match import Match
from src.pipelines.match_pipeline import MatchPipeline
from src.tasks._async_runner import run_async
from src.utils.db import SessionLocal, session_scope

logger = structlog.get_logger(__name__)

# Time windows that drive `dispatch_dynamic_jobs`.
_LIVE_LOOKAHEAD = timedelta(hours=4)  # treat anything starting in 4h as "live now"
_POST_MATCH_DELAY = timedelta(hours=2)
_ODDS_CLOSE_WINDOW = timedelta(hours=2)
_ODDS_PRE_WINDOW = timedelta(hours=24)
# Pre-kickoff prediction window: enqueue a fresh prediction for any scheduled
# match starting 3–5 days from now that doesn't already have one. Wider than
# the odds windows because predictions are cheaper to refresh and the user
# wants the score / 1×2 / over-under numbers visible well before kickoff.
_PREDICTION_PRE_WINDOW_LOWER = timedelta(days=3)
_PREDICTION_PRE_WINDOW_UPPER = timedelta(days=5)


# --- Periodic ---


@app.task(
    bind=True,
    name="match.sync_daily",
    max_retries=DEFAULT_MAX_RETRIES,
    retry_backoff=DEFAULT_RETRY_BACKOFF,
    retry_backoff_max=DEFAULT_RETRY_BACKOFF_MAX,
)
def sync_matches_daily(self) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    """Pull fixtures for every entry in `settings.ACTIVE_COMPETITIONS`."""
    try:
        return run_async(_sync_matches_daily_async())
    except Exception as exc:
        logger.exception("match_sync_daily_failed")
        raise self.retry(exc=exc) from exc


async def _sync_matches_daily_async() -> dict[str, Any]:
    producer = build_producer()
    summary: dict[str, Any] = {"competitions": []}
    try:
        async with ApiFootballAdapter() as adapter:
            pipeline = MatchPipeline(adapter, SessionLocal, producer=producer)
            for season_id in settings.ACTIVE_COMPETITIONS:
                result = await pipeline.run(season_id=season_id)
                summary["competitions"].append(
                    {
                        "season_id": season_id,
                        "fetched": result.fetched,
                        "inserted": result.inserted,
                        "errors": len(result.errors),
                    }
                )
    finally:
        producer.close()
    logger.info("match_sync_daily_completed", summary=summary)
    return summary


# --- On-demand: single in-progress match ---


@app.task(
    bind=True,
    name="match.sync_live",
    max_retries=DEFAULT_MAX_RETRIES,
    retry_backoff=DEFAULT_RETRY_BACKOFF,
)
def sync_matches_live(self, match_id: int) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    """Refresh one in-progress fixture's score / status."""
    try:
        return run_async(_sync_matches_live_async(match_id))
    except Exception as exc:
        logger.exception("match_sync_live_failed", match_id=match_id)
        raise self.retry(exc=exc) from exc


async def _sync_matches_live_async(match_id: int) -> dict[str, Any]:
    # The pipeline today re-syncs whole seasons; for a single live match we go
    # straight at the API-Football fixture endpoint and upsert directly.
    # Phase 2 will add a `MatchPipeline.run(match_external_id=...)` mode.
    producer = build_producer()
    try:
        async with ApiFootballAdapter() as adapter:
            detail = await adapter.fetch_match_detail(match_id)
    finally:
        producer.close()
    logger.info("match_live_fetched", match_id=match_id, status=detail.match.status)
    return {
        "match_id": match_id,
        "status": detail.match.status,
        "home_score": detail.match.home_score,
        "away_score": detail.match.away_score,
    }


# --- Periodic: dynamic dispatch ---


@app.task(name="match.dispatch_dynamic_jobs")
def dispatch_dynamic_jobs() -> dict[str, Any]:
    """Scan the matches calendar and fan out per-match work.

    Cheap when no matches are upcoming — the queries are indexed and bounded
    to short time windows. The fan-out targets named tasks in the other task
    modules (`stats.sync_post_match`, `odds.sync_pre_kickoff`, `odds.sync_pre_kickoff_frequent`,
    `match.sync_live`) — they're enqueued via `app.send_task` so this scanner
    doesn't import them at module-load time.
    """
    now = datetime.now(UTC)
    counts = {
        "live": 0,
        "post_match_stats": 0,
        "odds_pre": 0,
        "odds_close": 0,
        "predictions_pre_kickoff": 0,
    }

    with session_scope() as session:
        for match in _live_matches(session, now):
            app.send_task("match.sync_live", args=[match.id])
            counts["live"] += 1
        for match in _post_match_stats_candidates(session, now):
            app.send_task("stats.sync_post_match", args=[match.id])
            counts["post_match_stats"] += 1
        for match in _odds_pre_kickoff_candidates(session, now):
            app.send_task("odds.sync_pre_kickoff", args=[match.id])
            counts["odds_pre"] += 1
        for match in _odds_close_to_kickoff_candidates(session, now):
            app.send_task("odds.sync_pre_kickoff_frequent", args=[match.id])
            counts["odds_close"] += 1
        for match_id in _prediction_pre_kickoff_candidates(session, now):
            app.send_task("predictions.generate_pre_kickoff", args=[match_id])
            counts["predictions_pre_kickoff"] += 1

    logger.info("dispatch_dynamic_jobs_completed", **counts)
    return counts


# --- Calendar queries (kept private + small) ---


def _live_matches(session: Any, now: datetime) -> list[Match]:
    stmt = (
        select(Match)
        .where(
            Match.status.in_(("scheduled", "live")),
            Match.match_date <= now,
            Match.match_date >= now - _LIVE_LOOKAHEAD,
        )
        .order_by(Match.match_date)
    )
    return list(session.scalars(stmt))


def _post_match_stats_candidates(session: Any, now: datetime) -> list[Match]:
    cutoff = now - _POST_MATCH_DELAY
    stmt = (
        select(Match)
        .where(
            Match.status == "finished",
            Match.match_date <= cutoff,
            Match.data_completeness < 50,  # crude proxy for "stats not yet ingested"
        )
        .order_by(Match.match_date)
        .limit(100)
    )
    return list(session.scalars(stmt))


def _odds_pre_kickoff_candidates(session: Any, now: datetime) -> list[Match]:
    stmt = (
        select(Match)
        .where(
            Match.status == "scheduled",
            Match.match_date > now + _ODDS_CLOSE_WINDOW,
            Match.match_date <= now + _ODDS_PRE_WINDOW,
        )
        .order_by(Match.match_date)
    )
    return list(session.scalars(stmt))


def _odds_close_to_kickoff_candidates(session: Any, now: datetime) -> list[Match]:
    stmt = (
        select(Match)
        .where(
            Match.status == "scheduled",
            Match.match_date > now,
            Match.match_date <= now + _ODDS_CLOSE_WINDOW,
        )
        .order_by(Match.match_date)
    )
    return list(session.scalars(stmt))


def _prediction_pre_kickoff_candidates(session: Any, now: datetime) -> list[int]:
    """Match ids in the [+3d, +5d] window that have no prediction yet.

    The existence check is on `predictions.match_id` regardless of
    `model_version` — once a match has any prediction, the rolling task is
    done with it. Operators who want to refresh after a re-train run
    `scripts.generate_predictions --force` instead.
    """
    from src.models.prediction import Prediction  # local: avoid heavy imports at module load

    stmt = (
        select(Match.id)
        .where(
            Match.status == "scheduled",
            Match.match_date >= now + _PREDICTION_PRE_WINDOW_LOWER,
            Match.match_date <= now + _PREDICTION_PRE_WINDOW_UPPER,
            ~select(Prediction.id)
            .where(Prediction.match_id == Match.id)
            .exists(),
        )
        .order_by(Match.match_date)
    )
    return [int(row[0]) for row in session.execute(stmt).all()]

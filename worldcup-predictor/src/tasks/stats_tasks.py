"""Celery tasks for stats / valuation / injury ingestion.

Stats tasks fall into three buckets:

- Per-match (`sync_post_match`, `sync_fbref_xg`) — fired by
  `match.dispatch_dynamic_jobs` once a match has been finished long enough for
  the upstream provider to publish stats.
- Periodic player data (`sync_injuries`, `sync_valuations`) — runs on the
  weekly Beat schedule defined in `celery_config`.

All tasks emit the standard data_source_logs row via the underlying pipeline.
"""
from __future__ import annotations

from typing import Any

import structlog

from src.adapters.api_football import ApiFootballAdapter
from src.adapters.fbref import FBrefAdapter
from src.adapters.transfermarkt import TransfermarktAdapter
from src.config.celery_config import (
    DEFAULT_MAX_RETRIES,
    DEFAULT_RETRY_BACKOFF,
    DEFAULT_RETRY_BACKOFF_MAX,
    app,
)
from src.events.producer import build_producer
from src.pipelines.stats_pipeline import StatsPipeline
from src.tasks._async_runner import run_async
from src.utils.db import SessionLocal

logger = structlog.get_logger(__name__)


# --- Per-match: post-match aggregate stats from API-Football ---


@app.task(
    bind=True,
    name="stats.sync_post_match",
    max_retries=DEFAULT_MAX_RETRIES,
    retry_backoff=DEFAULT_RETRY_BACKOFF,
    retry_backoff_max=DEFAULT_RETRY_BACKOFF_MAX,
)
def sync_stats_post_match(self, match_id: int) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    """Pull team-level stats for a finished match (typically 2h post-FT)."""
    try:
        return run_async(_sync_stats_post_match_async(match_id))
    except Exception as exc:
        logger.exception("stats_sync_post_match_failed", match_id=match_id)
        raise self.retry(exc=exc) from exc


async def _sync_stats_post_match_async(match_id: int) -> dict[str, Any]:
    producer = build_producer()
    try:
        async with ApiFootballAdapter() as adapter:
            pipeline = StatsPipeline(adapter, SessionLocal, producer=producer)
            result = await pipeline.run(match_id=match_id)
    finally:
        producer.close()
    logger.info(
        "stats_post_match_completed",
        match_id=match_id,
        inserted=result.inserted,
        skipped=result.skipped,
    )
    return {"match_id": match_id, "inserted": result.inserted}


# --- Per-match: FBref xG (6-12h post-FT, slower upstream) ---


@app.task(
    bind=True,
    name="stats.sync_fbref_xg",
    max_retries=DEFAULT_MAX_RETRIES,
    retry_backoff=DEFAULT_RETRY_BACKOFF,
    retry_backoff_max=DEFAULT_RETRY_BACKOFF_MAX,
)
def sync_fbref_xg(self, match_id: str) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    """Scrape the FBref match page for xG / shots / passing detail.

    `match_id` is FBref's 8-char match hex, *not* the internal `matches.id`.
    The orchestrator is responsible for the lookup.
    """
    try:
        return run_async(_sync_fbref_xg_async(match_id))
    except Exception as exc:
        logger.exception("fbref_xg_sync_failed", match_id=match_id)
        raise self.retry(exc=exc) from exc


async def _sync_fbref_xg_async(match_id: str) -> dict[str, Any]:
    async with FBrefAdapter() as adapter:
        detail = await adapter.fetch_match_detail(match_id)
    return {
        "match_id": match_id,
        "player_stats_count": len(detail.player_stats),
        "home_xg_present": detail.home_stats is not None and detail.home_stats.xg is not None,
    }


# --- Weekly: injuries (Tuesday + Friday 08:00) ---


@app.task(
    bind=True,
    name="stats.sync_injuries",
    max_retries=DEFAULT_MAX_RETRIES,
    retry_backoff=DEFAULT_RETRY_BACKOFF,
    retry_backoff_max=DEFAULT_RETRY_BACKOFF_MAX,
)
def sync_injuries(self) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    """Refresh the injury list across the active competitions' national teams.

    Phase-1 implementation logs a placeholder count. Concrete iteration over
    competing nations + per-team scrape is a Phase 2 deliverable: it requires
    a `competitions → participating_teams` mapping table that doesn't yet
    exist. Today's job exists so the schedule + alerting are wired end-to-end.
    """
    try:
        return run_async(_sync_injuries_async())
    except Exception as exc:
        logger.exception("sync_injuries_failed")
        raise self.retry(exc=exc) from exc


async def _sync_injuries_async() -> dict[str, Any]:
    async with TransfermarktAdapter() as adapter:
        healthy = await adapter.health_check()
    # TODO(Phase 2): iterate participating teams from competition_teams join.
    logger.info("sync_injuries_completed_stub", source_healthy=healthy)
    return {"injuries_fetched": 0, "source_healthy": healthy}


# --- Weekly: market valuations (Monday 08:00) ---


@app.task(
    bind=True,
    name="stats.sync_valuations",
    max_retries=DEFAULT_MAX_RETRIES,
    retry_backoff=DEFAULT_RETRY_BACKOFF,
    retry_backoff_max=DEFAULT_RETRY_BACKOFF_MAX,
)
def sync_valuations(self) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    """Refresh per-player Transfermarkt market values.

    Same Phase-1 caveat as `sync_injuries`: stub iteration. The Transfermarkt
    valuations endpoint takes a player id, so this loop will become
    ``for player_id in active_player_ids: adapter.fetch_valuations(player_id)``
    once Phase 2 builds the active-roster view.
    """
    try:
        return run_async(_sync_valuations_async())
    except Exception as exc:
        logger.exception("sync_valuations_failed")
        raise self.retry(exc=exc) from exc


async def _sync_valuations_async() -> dict[str, Any]:
    async with TransfermarktAdapter() as adapter:
        healthy = await adapter.health_check()
    # TODO(Phase 2): walk Player rows where current_team_id IN (participating).
    logger.info("sync_valuations_completed_stub", source_healthy=healthy)
    return {"valuations_fetched": 0, "source_healthy": healthy}

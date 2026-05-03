"""Celery tasks for bookmaker-odds ingestion.

Two cadences:

- `sync_pre_kickoff(match_id)` — hourly, for matches starting in the next 2–24h.
- `sync_pre_kickoff_frequent(match_id)` — every 10 min, for matches starting
  in the next 2h. Both are kicked off by `match.dispatch_dynamic_jobs`; they
  do *not* sit in the static beat schedule.

Both dispatch to the same OddsApi adapter; the only difference is cadence.
"""
from __future__ import annotations

from typing import Any

import structlog

from src.adapters.odds_api import OddsApiAdapter
from src.config.celery_config import (
    DEFAULT_MAX_RETRIES,
    DEFAULT_RETRY_BACKOFF,
    DEFAULT_RETRY_BACKOFF_MAX,
    app,
)
from src.events.producer import build_producer
from src.pipelines.odds_pipeline import OddsPipeline
from src.tasks._async_runner import run_async
from src.utils.db import SessionLocal

logger = structlog.get_logger(__name__)


@app.task(
    bind=True,
    name="odds.sync_pre_kickoff",
    max_retries=DEFAULT_MAX_RETRIES,
    retry_backoff=DEFAULT_RETRY_BACKOFF,
    retry_backoff_max=DEFAULT_RETRY_BACKOFF_MAX,
)
def sync_odds_hourly(self, match_id: str) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    """Hourly odds pull for matches kicking off within the next 24h."""
    try:
        return run_async(_sync_odds_async(match_id))
    except Exception as exc:
        logger.exception("odds_hourly_failed", match_id=match_id)
        raise self.retry(exc=exc) from exc


@app.task(
    bind=True,
    name="odds.sync_pre_kickoff_frequent",
    max_retries=DEFAULT_MAX_RETRIES,
    retry_backoff=DEFAULT_RETRY_BACKOFF,
    retry_backoff_max=DEFAULT_RETRY_BACKOFF_MAX,
)
def sync_odds_frequent(self, match_id: str) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    """High-frequency odds pull for matches kicking off within the next 2h."""
    try:
        return run_async(_sync_odds_async(match_id))
    except Exception as exc:
        logger.exception("odds_frequent_failed", match_id=match_id)
        raise self.retry(exc=exc) from exc


async def _sync_odds_async(match_id: str) -> dict[str, Any]:
    producer = build_producer()
    try:
        async with OddsApiAdapter() as adapter:
            pipeline = OddsPipeline(adapter, SessionLocal, producer=producer)
            result = await pipeline.run(match_id=match_id)
    finally:
        producer.close()
    logger.info(
        "odds_sync_completed",
        match_id=match_id,
        inserted=result.inserted,
        skipped=result.skipped,
    )
    return {
        "match_id": match_id,
        "inserted": result.inserted,
        "skipped": result.skipped,
    }

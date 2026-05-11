"""Operational tasks: log retention, data-quality checks, manual backfills.

`check_data_completeness` is the single most important operational signal: it
emits a `data.quality.alert` event when any of five thresholds trip, which
the on-call dashboard consumes. The five checks themselves live in
`src.utils.quality_checks` so the CLI (`scripts/validate_data.py`) can reuse
the same logic.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import structlog

from src.config.celery_config import (
    DEFAULT_MAX_RETRIES,
    DEFAULT_RETRY_BACKOFF,
    app,
)
from src.events.producer import build_producer
from src.events.topics import TOPIC_DATA_QUALITY_ALERT
from src.models.data_source_log import DataSourceLog
from src.utils.db import session_scope
from src.utils.quality_checks import run_all

logger = structlog.get_logger(__name__)

LOG_RETENTION_DAYS: int = 90


# --- Log retention ---


@app.task(
    bind=True,
    name="maintenance.cleanup_old_logs",
    max_retries=DEFAULT_MAX_RETRIES,
    retry_backoff=DEFAULT_RETRY_BACKOFF,
)
def cleanup_old_logs(self) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    """Delete `data_source_logs` rows older than `LOG_RETENTION_DAYS`."""
    try:
        cutoff = datetime.now(UTC) - timedelta(days=LOG_RETENTION_DAYS)
        with session_scope() as session:
            count = (
                session.query(DataSourceLog)
                .filter(DataSourceLog.started_at < cutoff)
                .delete(synchronize_session=False)
            )
        logger.info("logs_cleaned_up", deleted=count, cutoff=cutoff.isoformat())
        return {"deleted": count, "cutoff": cutoff.isoformat()}
    except Exception as exc:
        logger.exception("cleanup_old_logs_failed")
        raise self.retry(exc=exc) from exc


# --- Data-quality dashboard ---


@app.task(
    bind=True,
    name="maintenance.check_data_completeness",
    max_retries=DEFAULT_MAX_RETRIES,
    retry_backoff=DEFAULT_RETRY_BACKOFF,
)
def check_data_completeness(self) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    """Run all five quality checks and emit alerts for any that trip."""
    producer = build_producer()
    report: dict[str, Any] = {}
    try:
        with session_scope() as session:
            results = run_all(session)
        for payload in results:
            report[payload.check_name] = {
                "severity": payload.severity,
                "affected": payload.affected_count,
                "message": payload.message,
            }
            if payload.severity != "info":
                producer.publish(
                    event_type=TOPIC_DATA_QUALITY_ALERT,
                    key=payload.check_name,
                    payload=payload,
                )
    finally:
        producer.close()
    logger.info("data_completeness_report", report=report)
    return report


# --- Manual backfill trigger ---


@app.task(name="maintenance.trigger_backfill")
def trigger_backfill(source: str, match_ids: list[int]) -> dict[str, Any]:
    """Manually re-enqueue per-match work for `match_ids` against `source`.

    Routes to the right per-match task based on `source`:
        - 'api_football' → stats.sync_post_match
        - 'fbref'        → stats.sync_fbref_xg
        - 'odds_api'     → odds.sync_pre_kickoff
    """
    routing = {
        "api_football": "stats.sync_post_match",
        "fbref": "stats.sync_fbref_xg",
        "odds_api": "odds.sync_pre_kickoff",
    }
    target = routing.get(source)
    if target is None:
        raise ValueError(f"Unknown source for backfill: {source!r}")

    for match_id in match_ids:
        app.send_task(target, args=[match_id])
    logger.info("backfill_triggered", source=source, count=len(match_ids), task=target)
    return {"source": source, "task": target, "enqueued": len(match_ids)}

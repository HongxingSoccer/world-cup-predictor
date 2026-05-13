"""Celery application + Beat schedule for the ingestion worker.

Workers are started with ``celery -A src.config.celery_config:app worker``,
and the beat scheduler with ``celery -A src.config.celery_config:app beat``.
The Docker compose stack runs both as separate services (`ingestion-worker` /
`ingestion-beat`) so they can be scaled independently.

The beat_schedule below covers the *static* periodic jobs spelled out in the
Phase-1 spec. Per-match dynamic scheduling (live-score polling, pre-match odds
sync) is handled by `dispatch_dynamic_jobs` — a fast scanner that runs every
five minutes and fans out short-lived tasks based on the matches calendar.
"""
from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from src.config.settings import settings

app = Celery(
    "wcp-ingestion",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "src.tasks.match_tasks",
        "src.tasks.stats_tasks",
        "src.tasks.odds_tasks",
        "src.tasks.maintenance_tasks",
        "src.tasks.settlement_tasks",
        "src.tasks.card_tasks",
        "src.tasks.live_monitor_tasks",
        "src.tasks.arb_scanner_tasks",
    ],
)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Tasks should fail loudly rather than silently swallow exceptions.
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    # Keep result records short-lived to avoid Redis growth.
    result_expires=24 * 3600,
)

# --- Task routing: send settlement/card tasks to dedicated queues so worker
# instances can subscribe to them and remain isolated from the general ingest
# pipeline. Default tasks remain on the 'celery' queue.
app.conf.task_routes = {
    "settlement.*": {"queue": "settlement"},
    "card.*": {"queue": "card"},
    "phase4.generate_match_report": {"queue": "reports"},
    # M9.5 live-hedge monitor — runs on its own queue so the 60s scan
    # cadence doesn't compete with the general ingestion pipeline.
    "live_monitor.*": {"queue": "live_monitor"},
    # M10 arbitrage scanner — own queue, runs every 60s and pushes alerts
    # to users matching the per-user watchlist filter.
    "arb_scanner.*": {"queue": "arb_scanner"},
}

# --- Beat schedule (static periodic jobs) ---
#
# Times are UTC. Anything per-match (live scores, pre-kickoff odds polling)
# is dispatched dynamically by `dispatch_dynamic_jobs` rather than pinned in
# beat — those jobs only matter on match days, and match days are sparse.

app.conf.beat_schedule = {
    "match.sync_daily": {
        "task": "match.sync_daily",
        "schedule": crontab(hour=6, minute=0),
    },
    # The dynamic-dispatch scanner runs frequently and decides at runtime
    # whether to enqueue any per-match work. Cheap when the calendar is empty.
    "match.dispatch_dynamic_jobs": {
        "task": "match.dispatch_dynamic_jobs",
        "schedule": crontab(minute="*/5"),
    },
    "stats.sync_injuries": {
        "task": "stats.sync_injuries",
        "schedule": crontab(day_of_week="tue,fri", hour=8, minute=0),
    },
    "stats.sync_valuations": {
        "task": "stats.sync_valuations",
        "schedule": crontab(day_of_week="mon", hour=8, minute=0),
    },
    "maintenance.cleanup_old_logs": {
        "task": "maintenance.cleanup_old_logs",
        "schedule": crontab(day_of_week="sun", hour=3, minute=0),
    },
    "maintenance.check_data_completeness": {
        "task": "maintenance.check_data_completeness",
        "schedule": crontab(hour=12, minute=0),
    },
    # Phase-3 hourly settlement sweep — finds matches that finished ≥ 2h ago
    # and dispatches per-match settlement work.
    "settlement.scan_finished_matches": {
        "task": "settlement.scan_finished_matches",
        "schedule": crontab(minute=15),
    },
    # Tournament simulation runs every day at 03:30 UTC — late enough that
    # any new predictions ingested in the prior day are visible, early enough
    # that the dashboard is fresh by morning. Cheap (a few seconds per run).
    "tournament.simulate_daily": {
        "task": "tournament.simulate_daily",
        "schedule": crontab(hour=3, minute=30),
    },
    # M9.5 — live-hedge monitor scans active positions every 60s and
    # fires hedge_window alerts when a position trips the detector.
    "live_monitor.scan_active_positions": {
        "task": "live_monitor.scan_active_positions",
        "schedule": 60.0,
    },
    # M10 — cross-platform arbitrage scanner. 60s cadence; cheap when
    # the bookmaker market is well-aligned (no arb persisted).
    "arb_scanner.scan_for_arbitrage": {
        "task": "arb_scanner.scan_for_arbitrage",
        "schedule": 60.0,
    },
}

# Default retry policy applied via task decorator; centralized constants here
# so the four task modules can reference the same numbers.
DEFAULT_MAX_RETRIES: int = 3
DEFAULT_RETRY_BACKOFF: bool = True
DEFAULT_RETRY_BACKOFF_MAX: int = 600  # cap exponential backoff at 10 min

"""Celery task modules.

Importing this package registers tasks with the Celery app instance defined
in `src.config.celery_config`. The Celery worker entrypoint
(`celery -A src.config.celery_config:app worker`) loads them via the
`include=[...]` list configured on the app.
"""
from . import (
    arb_scanner_tasks,
    card_tasks,
    live_monitor_tasks,
    maintenance_tasks,
    match_tasks,
    odds_tasks,
    prediction_tasks,
    settlement_tasks,
    stats_tasks,
)

__all__ = [
    "arb_scanner_tasks",
    "card_tasks",
    "live_monitor_tasks",
    "maintenance_tasks",
    "match_tasks",
    "odds_tasks",
    "prediction_tasks",
    "settlement_tasks",
    "stats_tasks",
]

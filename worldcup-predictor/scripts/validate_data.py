"""CLI wrapper around the data-completeness checks.

Re-uses the same five checks the Celery `maintenance.check_data_completeness`
task runs, but prints them as a human-readable report on stdout (plus a
non-zero exit code when any check is non-info). Useful in CI / cron / manual
triage where Flower isn't convenient.

Usage:
    python -m scripts.validate_data
    python -m scripts.validate_data --json
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone

import structlog

from src.events.schemas import DataQualityAlertPayload
from src.utils.db import session_scope
from src.utils.logging import configure_logging
from src.utils.quality_checks import run_all

logger = structlog.get_logger(__name__)

_SEVERITY_RANK: dict[str, int] = {"info": 0, "warning": 1, "critical": 2}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit results as JSON instead of a formatted table.",
    )
    return parser.parse_args()


async def main_async(args: argparse.Namespace) -> int:
    now = datetime.now(timezone.utc)
    with session_scope() as session:
        results = run_all(session, now=now)

    if args.json:
        print(json.dumps([r.model_dump() for r in results], indent=2, default=str))
    else:
        _print_report(results)

    worst = max((_SEVERITY_RANK[r.severity] for r in results), default=0)
    return 0 if worst == 0 else 1


def _print_report(results: list[DataQualityAlertPayload]) -> None:
    print(f"{'CHECK':<28} {'SEVERITY':<10} {'AFFECTED':>10}  MESSAGE")
    print("-" * 100)
    for r in results:
        print(f"{r.check_name:<28} {r.severity:<10} {r.affected_count:>10}  {r.message}")


if __name__ == "__main__":
    configure_logging(json_logs=False)
    sys.exit(asyncio.run(main_async(parse_args())))

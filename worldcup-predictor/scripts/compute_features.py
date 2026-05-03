"""Offline feature-computation CLI.

Walks every finished match in a date window, computes the v1 feature vector,
upserts the row into `match_features`, and dumps the full table to a Parquet
file at the end. Idempotent — re-running just refreshes existing rows in place.

Usage:
    python -m scripts.compute_features \\
        --feature-version v1 \\
        --start-date 2022-11-01 \\
        --end-date   2026-05-01 \\
        --output     data/features/v1.parquet
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, time, timezone
from pathlib import Path

import structlog
from sqlalchemy import select
from tqdm import tqdm

from src.ml.features.pipeline import DEFAULT_FEATURE_VERSION, FeaturePipeline
from src.models.match import Match
from src.utils.db import session_scope
from src.utils.logging import configure_logging

logger = structlog.get_logger(__name__)

DEFAULT_OUTPUT = Path("data/features") / f"{DEFAULT_FEATURE_VERSION}.parquet"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feature-version", default=DEFAULT_FEATURE_VERSION)
    parser.add_argument(
        "--start-date",
        default="2022-11-01",
        help="Inclusive lower bound on match_date (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--end-date",
        default=datetime.now(timezone.utc).date().isoformat(),
        help="Exclusive upper bound on match_date (YYYY-MM-DD); defaults to today.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Parquet output path. Default: {DEFAULT_OUTPUT}.",
    )
    parser.add_argument(
        "--no-parquet",
        action="store_true",
        help="Skip the Parquet export step (DB upserts only).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    start = _parse_date(args.start_date)
    end = _parse_date(args.end_date)
    if start >= end:
        logger.error("invalid_date_window", start=str(start), end=str(end))
        return 2

    with session_scope() as session:
        pipeline = FeaturePipeline(session, feature_version=args.feature_version)
        match_rows = _eligible_matches(session, start, end)

        logger.info(
            "compute_features_started",
            window=f"{start.isoformat()}..{end.isoformat()}",
            match_count=len(match_rows),
            feature_version=args.feature_version,
        )

        for match_id, home_score, away_score in tqdm(match_rows, desc="computing features"):
            features = pipeline.compute_for_match(match_id)
            labels = _labels_from_scores(home_score, away_score)
            pipeline.save_to_db(match_id, features, labels)

        if not args.no_parquet:
            written = pipeline.export_to_parquet(args.output)
            logger.info("parquet_written", path=str(args.output), rows=written)

    logger.info("compute_features_completed")
    return 0


def _eligible_matches(
    session,  # type: ignore[no-untyped-def]
    start: datetime,
    end: datetime,
) -> list[tuple[int, int | None, int | None]]:
    stmt = (
        select(Match.id, Match.home_score, Match.away_score)
        .where(
            Match.status == "finished",
            Match.match_date >= start,
            Match.match_date < end,
        )
        .order_by(Match.match_date)
    )
    return [(row.id, row.home_score, row.away_score) for row in session.execute(stmt).all()]


def _labels_from_scores(
    home_score: int | None, away_score: int | None
) -> dict[str, int | str | None]:
    if home_score is None or away_score is None:
        return {"home_score": None, "away_score": None, "result": None}
    if home_score > away_score:
        result = "H"
    elif home_score < away_score:
        result = "A"
    else:
        result = "D"
    return {"home_score": home_score, "away_score": away_score, "result": result}


def _parse_date(raw: str) -> datetime:
    parts = raw.split("-")
    return datetime.combine(
        datetime(int(parts[0]), int(parts[1]), int(parts[2])).date(),
        time.min,
        tzinfo=timezone.utc,
    )


if __name__ == "__main__":
    configure_logging(json_logs=False)
    sys.exit(main())

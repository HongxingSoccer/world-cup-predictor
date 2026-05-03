"""One-shot importer for the martj42/international_results dataset.

Usage:
    python -m scripts.import_static_data --csv-url <URL or file path> [--year 2026]

Bootstraps three things, in order:

    1. A `competitions` row per unique tournament name in the CSV.
    2. One `seasons` row per (competition, year) referenced.
    3. National-team `teams` rows for every distinct home/away name.

Then, with the catalog populated, runs `MatchPipeline` against the same CSV
to insert the matches themselves. Idempotent — re-runs upsert on the existing
rows rather than producing duplicates (catalog rows hit the unique
constraints, matches dedupe on the synthetic external id).
"""
from __future__ import annotations

import argparse
import asyncio

import structlog
from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.adapters.static_data import StaticDataAdapter
from src.dto.match import MatchDTO
from src.events.producer import build_producer
from src.models.competition import Competition
from src.models.season import Season
from src.models.team import Team
from src.pipelines.match_pipeline import MatchPipeline
from src.utils.db import SessionLocal, session_scope
from src.utils.logging import configure_logging

logger = structlog.get_logger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv-url", default=None, help="HTTPS or local path to results.csv")
    parser.add_argument(
        "--year",
        default="all",
        help="Year to ingest (e.g. 2024) or 'all' (default).",
    )
    parser.add_argument(
        "--no-kafka",
        action="store_true",
        help="Skip Kafka emission (useful for offline backfills).",
    )
    return parser.parse_args()


async def main_async(args: argparse.Namespace) -> None:
    adapter_kwargs = {"csv_url": args.csv_url} if args.csv_url else {}
    async with StaticDataAdapter(**adapter_kwargs) as adapter:
        # 1. Pull every match DTO so we can derive the catalog from it.
        dtos = await adapter.fetch_matches(args.year)
        if not dtos:
            logger.warning("no_matches_in_csv", year=args.year)
            return

        bootstrap_catalog(dtos)

        # 2. Run the pipeline on the same DTO list. We build a producer here
        #    rather than in the pipeline so the script can disable Kafka.
        producer = build_producer(enabled=not args.no_kafka)
        pipeline = _PreloadedMatchPipeline(adapter, SessionLocal, producer=producer, dtos=dtos)
        try:
            result = await pipeline.run(season_id=args.year)
        finally:
            producer.close()

    logger.info(
        "static_import_completed",
        year=args.year,
        fetched=result.fetched,
        inserted=result.inserted,
        skipped=result.skipped,
        errors=len(result.errors),
    )


def bootstrap_catalog(dtos: list[MatchDTO]) -> None:
    """Insert competitions / seasons / teams referenced by `dtos` (no-op on conflict)."""
    competitions = {dto.competition_name for dto in dtos}
    teams = {dto.home_team_name for dto in dtos} | {dto.away_team_name for dto in dtos}
    season_pairs = {(dto.competition_name, dto.season_year) for dto in dtos}

    with session_scope() as session:
        for name in sorted(competitions):
            session.execute(
                pg_insert(Competition)
                .values(name=name, competition_type="national", is_active=True)
                .on_conflict_do_nothing(index_elements=["api_football_id"])
            )
        # Seasons need the competition id, so commit competitions first.
        session.flush()
        comp_ids = {row.name: row.id for row in session.query(Competition).all()}
        for comp_name, year in sorted(season_pairs):
            session.execute(
                pg_insert(Season)
                .values(competition_id=comp_ids[comp_name], year=year)
                .on_conflict_do_nothing(constraint="uq_seasons_competition_year")
            )
        for name in sorted(teams):
            session.add(Team(name=name, team_type="national"))
            try:
                session.flush()
            except Exception:
                session.rollback()  # name collisions on retries
    logger.info(
        "catalog_bootstrapped",
        competitions=len(competitions),
        seasons=len(season_pairs),
        teams=len(teams),
    )


class _PreloadedMatchPipeline(MatchPipeline):
    """MatchPipeline variant that uses an in-memory DTO list instead of re-fetching."""

    def __init__(self, *args: object, dtos: list[MatchDTO], **kwargs: object) -> None:  # type: ignore[no-untyped-def]
        super().__init__(*args, **kwargs)
        self._preloaded = dtos

    async def fetch_dtos(self, **kwargs: object) -> list[MatchDTO]:  # type: ignore[override]
        return self._preloaded


if __name__ == "__main__":
    configure_logging(json_logs=False)
    args = parse_args()
    asyncio.run(main_async(args))

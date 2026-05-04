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
from sqlalchemy import select, tuple_
from sqlalchemy.dialects.postgresql import Insert as PGInsert
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from src.adapters.static_data import StaticDataAdapter
from src.dto.match import MatchDTO
from src.events.producer import build_producer
from src.models.competition import Competition
from src.models.match import Match
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
    """Insert competitions / seasons / teams referenced by `dtos` (idempotent).

    The static dataset has no external ids, and `competitions.name` /
    `teams.name` carry no DB-level unique constraint, so we look up by name
    and only insert rows that don't already exist.
    """
    competitions = {dto.competition_name for dto in dtos}
    teams = {dto.home_team_name for dto in dtos} | {dto.away_team_name for dto in dtos}
    season_pairs = {(dto.competition_name, dto.season_year) for dto in dtos}

    with session_scope() as session:
        existing_comps = {row.name for row in session.query(Competition.name).all()}
        for name in sorted(competitions - existing_comps):
            session.add(Competition(name=name, competition_type="national", is_active=True))
        session.flush()
        comp_ids = {row.name: row.id for row in session.query(Competition).all()}
        for comp_name, year in sorted(season_pairs):
            session.execute(
                pg_insert(Season)
                .values(competition_id=comp_ids[comp_name], year=year)
                .on_conflict_do_nothing(constraint="uq_seasons_competition_year")
            )
        existing_teams = {row.name for row in session.query(Team.name).all()}
        for name in sorted(teams - existing_teams):
            session.add(Team(name=name, team_type="national"))
    logger.info(
        "catalog_bootstrapped",
        competitions=len(competitions),
        seasons=len(season_pairs),
        teams=len(teams),
    )


class _PreloadedMatchPipeline(MatchPipeline):
    """MatchPipeline variant that uses an in-memory DTO list instead of re-fetching.

    The static dataset has no `api_football_id` for any row, so the parent's
    `ON CONFLICT (api_football_id)` upsert can't infer a constraint (the unique
    index is partial — `WHERE api_football_id IS NOT NULL`). We instead dedupe
    on the natural key (home_team_id, away_team_id, match_date) — both within
    the incoming batch and against existing rows — then issue a plain INSERT.
    """

    def __init__(self, *args: object, dtos: list[MatchDTO], **kwargs: object) -> None:  # type: ignore[no-untyped-def]
        super().__init__(*args, **kwargs)
        self._preloaded = dtos

    async def fetch_dtos(self, **kwargs: object) -> list[MatchDTO]:  # type: ignore[override]
        return self._preloaded

    def resolve_and_map(self, session: Session, dtos: list[MatchDTO]) -> list[dict]:  # type: ignore[override]
        rows = super().resolve_and_map(session, dtos)
        # Dedupe within batch on (home, away, date).
        seen: set[tuple] = set()
        unique: list[dict] = []
        for row in rows:
            key = (row["home_team_id"], row["away_team_id"], row["match_date"])
            if key in seen:
                continue
            seen.add(key)
            unique.append(row)
        # Drop rows that already exist in DB.
        if not unique:
            return unique
        keys = list(seen)
        existing = set(
            session.execute(
                select(Match.home_team_id, Match.away_team_id, Match.match_date).where(
                    tuple_(Match.home_team_id, Match.away_team_id, Match.match_date).in_(keys)
                )
            ).all()
        )
        return [
            row
            for row in unique
            if (row["home_team_id"], row["away_team_id"], row["match_date"]) not in existing
        ]

    def build_upsert(self, rows: list[dict]) -> PGInsert:  # type: ignore[override]
        # Plain insert — uniqueness is enforced by the pre-filter above.
        return pg_insert(Match).values(rows)


if __name__ == "__main__":
    configure_logging(json_logs=False)
    args = parse_args()
    asyncio.run(main_async(args))

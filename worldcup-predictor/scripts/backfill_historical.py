"""End-to-end historical backfill orchestrator.

Run once per fresh database to populate every Phase-1 table from public data.
Steps execute in dependency order; each is idempotent so the script can be
re-run with ``--step`` to resume from a specific stage.

Usage:
    python -m scripts.backfill_historical --from 2022-11
    python -m scripts.backfill_historical --from 2022-11 --step 5

Steps:
    1  teams           Bootstrap national teams from static data.
    2  players         Pull player rosters per team (API-Football).
    3  matches         Backfill fixtures + scores (API-Football).
    4  match_stats     Backfill team-level stats (API-Football).
    5  fbref_xg        Layer FBref xG / shots on top of API-Football stats.
    6  valuations      Pull Transfermarkt valuations + injuries.
    7  odds_history    Pull historical odds from OddsPortal (Phase 2 stub).
    8  elo             Compute Elo ratings for every finished match.
    9  validate        Run the data-completeness checks.

Phase 1 implements steps 1, 3, 8, 9 fully; the rest log a placeholder so the
orchestrator's contract stays stable as the underlying adapters mature.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime, timezone

import structlog
from sqlalchemy import func

from src.config.settings import settings
from src.utils.db import session_scope
from src.utils.elo import backfill_elo_ratings
from src.utils.logging import configure_logging

logger = structlog.get_logger(__name__)

ALL_STEPS: tuple[str, ...] = (
    "teams",
    "players",
    "matches",
    "match_stats",
    "fbref_xg",
    "valuations",
    "odds_history",
    "elo",
    "validate",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from", dest="from_year_month", default="2022-11")
    parser.add_argument(
        "--step",
        type=int,
        default=1,
        choices=range(1, len(ALL_STEPS) + 1),
        metavar=f"1..{len(ALL_STEPS)}",
        help="Resume from this 1-indexed step (default: 1).",
    )
    parser.add_argument(
        "--only-step",
        type=int,
        default=None,
        choices=range(1, len(ALL_STEPS) + 1),
        metavar=f"1..{len(ALL_STEPS)}",
        help="Run exactly this single step and stop. Overrides --step's range.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help=(
            "Per-step processing cap. Currently respected by step 4 "
            "(match_stats) — useful for piloting against the API-Football "
            "free-tier 100 req/day quota before scaling up."
        ),
    )
    return parser.parse_args()


async def main_async(args: argparse.Namespace) -> None:
    start_year = int(args.from_year_month.split("-")[0])

    runners = (
        _step_teams,
        _step_players,
        _step_matches,
        _step_match_stats,
        _step_fbref_xg,
        _step_valuations,
        _step_odds_history,
        _step_elo,
        _step_validate,
    )

    for index, runner in enumerate(runners, start=1):
        if args.only_step is not None and index != args.only_step:
            continue
        if args.only_step is None and index < args.step:
            logger.info("backfill_step_skipped", step=index, name=ALL_STEPS[index - 1])
            continue
        logger.info("backfill_step_started", step=index, name=ALL_STEPS[index - 1])
        if index == 4:  # match_stats — only step that respects --limit today
            await runner(start_year, limit=args.limit)
        else:
            await runner(start_year)
        logger.info("backfill_step_completed", step=index, name=ALL_STEPS[index - 1])


# --- Step implementations (one per file is overkill for stubs) ---


async def _step_teams(start_year: int) -> None:
    # Defer to the dedicated importer for the real work; calling it inline
    # keeps the orchestrator the single entry point.
    from scripts.import_static_data import main_async as static_import_main

    fake_args = argparse.Namespace(csv_url=None, year="all", no_kafka=True)
    await static_import_main(fake_args)


async def _step_players(start_year: int) -> None:
    # TODO(Phase 2): iterate participating teams via API-Football /players?team=...
    logger.info("players_backfill_stub", note="implement via PlayerPipeline")


async def _step_matches(start_year: int) -> None:
    from src.adapters.api_football import ApiFootballAdapter
    from src.events.producer import build_producer
    from src.models.competition import Competition
    from src.models.season import Season
    from src.pipelines.match_pipeline import MatchPipeline
    from src.utils.db import SessionLocal

    producer = build_producer(enabled=False)
    try:
        async with ApiFootballAdapter() as adapter:
            pipeline = MatchPipeline(adapter, SessionLocal, producer=producer)
            for season_id in settings.ACTIVE_COMPETITIONS:
                # season_id is "league:year"; we only resync seasons >= start_year
                year = int(season_id.split(":")[1])
                if year < start_year:
                    continue
                # Probe one fixture to learn the canonical competition name
                # used by API-Football, then upsert competition + season so
                # MatchPipeline._resolve_season succeeds.
                dtos = await adapter.fetch_matches(season_id)
                if not dtos:
                    logger.warning("backfill_no_fixtures", season=season_id)
                    continue
                comp_name = dtos[0].competition_name
                with SessionLocal() as session:
                    comp = session.query(Competition).filter(Competition.name == comp_name).first()
                    if comp is None:
                        comp = Competition(name=comp_name, competition_type="national", is_active=True)
                        session.add(comp)
                        session.flush()
                    if not session.query(Season).filter(
                        Season.competition_id == comp.id, Season.year == year
                    ).first():
                        session.add(Season(competition_id=comp.id, year=year))
                    session.commit()
                # Now run the pipeline (will hit the API a second time — cheap).
                result = await pipeline.run(season_id=season_id)
                logger.info(
                    "matches_backfilled",
                    season=season_id,
                    competition=comp_name,
                    fetched=result.fetched,
                    inserted=result.inserted,
                    skipped=result.skipped,
                )
    finally:
        producer.close()


async def _step_match_stats(start_year: int, *, limit: int | None = None) -> None:
    """Iterate finished matches with an API-Football fixture id and pull
    team-level stats (possession / shots / xG / etc.) into ``match_stats``.

    Idempotent on two levels: the script skips matches that already have stats
    for both teams, and ``StatsPipeline.build_upsert`` does ``ON CONFLICT DO
    UPDATE`` so partial coverage gets healed on re-run. Matches without
    ``api_football_id`` are skipped silently — populating that mapping is a
    separate concern (see ``_step_matches`` for the API-Football re-ingest path).

    Args:
        start_year: Earliest match year to consider.
        limit: Stop after processing this many matches. Use this aggressively
            on the API-Football free tier (100 req/day, ~3 reqs per match).
    """
    from sqlalchemy import select

    from src.adapters.api_football import ApiFootballAdapter
    from src.events.producer import build_producer
    from src.models.match import Match
    from src.models.match_stats import MatchStats
    from src.pipelines.stats_pipeline import StatsPipeline
    from src.utils.db import SessionLocal, session_scope

    start_dt = datetime(start_year, 1, 1, tzinfo=timezone.utc)

    with session_scope() as session:
        already = set(
            row[0]
            for row in session.execute(
                select(MatchStats.match_id).group_by(MatchStats.match_id).having(
                    func.count(MatchStats.team_id) >= 2
                )
            ).all()
        )
        candidates = session.execute(
            select(Match.id, Match.api_football_id)
            .where(
                Match.status == "finished",
                Match.match_date >= start_dt,
                Match.api_football_id.isnot(None),
            )
            .order_by(Match.match_date.desc())
        ).all()

    todo: list[tuple[int, int]] = [
        (mid, api_id) for mid, api_id in candidates if mid not in already
    ]
    if limit is not None and limit > 0:
        todo = todo[:limit]
    logger.info(
        "match_stats_backfill_planned",
        candidates=len(candidates),
        already_done=len(already),
        todo=len(todo),
        limit=limit,
    )
    if not todo:
        return

    producer = build_producer(enabled=False)
    failed = 0
    try:
        async with ApiFootballAdapter() as adapter:
            pipeline = StatsPipeline(adapter, SessionLocal, producer=producer)
            for index, (mid, api_id) in enumerate(todo, start=1):
                try:
                    result = await pipeline.run(match_id=api_id)
                except Exception as exc:  # noqa: BLE001 — keep the batch going
                    failed += 1
                    logger.warning(
                        "match_stats_failed",
                        match_id=mid,
                        api_football_id=api_id,
                        error=repr(exc),
                    )
                    continue
                if index % 25 == 0 or index == len(todo):
                    logger.info(
                        "match_stats_progress",
                        done=index,
                        total=len(todo),
                        failed=failed,
                        last_inserted=result.inserted,
                    )
    finally:
        producer.close()
    logger.info("match_stats_backfill_done", processed=len(todo), failed=failed)


async def _step_fbref_xg(start_year: int) -> None:
    # TODO(Phase 2): cross-reference matches → FBref ids, run FBref xG sync.
    logger.info("fbref_xg_backfill_stub", note="implement adapter id mapping")


async def _step_valuations(start_year: int) -> None:
    # TODO(Phase 2): walk Player rows, call TransfermarktAdapter.fetch_valuations.
    logger.info("valuations_backfill_stub")


async def _step_odds_history(start_year: int) -> None:
    # TODO(Phase 2): OddsPortal Playwright scrape → OddsPipeline.
    logger.info("odds_history_backfill_stub")


async def _step_elo(start_year: int) -> None:
    """Compute Elo ratings on every finished match. Idempotent appends to elo_ratings."""
    with session_scope() as session:
        rows_written = backfill_elo_ratings(session)
    logger.info("elo_backfill_done", rows_written=rows_written)


async def _step_validate(start_year: int) -> None:
    # Cheaper to call the script as a function than to spawn a subprocess.
    from scripts.validate_data import main_async as validate_main

    await validate_main(argparse.Namespace(json=False))


if __name__ == "__main__":
    configure_logging(json_logs=False)
    try:
        asyncio.run(main_async(parse_args()))
    except KeyboardInterrupt:
        logger.warning("backfill_interrupted")
        sys.exit(130)

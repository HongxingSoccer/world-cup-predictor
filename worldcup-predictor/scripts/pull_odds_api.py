"""Pull live fixtures + bookmaker odds from The Odds API.

This is the single entry point that fills the Phase-1 stub left in
``backfill_historical._step_odds_history``. It sidesteps the OddsPipeline /
MatchPipeline duo because OddsAPI events don't carry an integer
``api_football_id`` — instead we resolve teams by name and dedupe matches by
``(home_id, away_id, match_date)``.

Behaviour
---------
For each ``ODDS_API_SPORT_KEYS`` entry:

1. ``GET /v4/sports/{sport_key}/odds`` (1 quota call). Returns up to ~50
   upcoming events with bookmakers + h2h markets inlined.
2. For each event:

   - Resolve home/away team via :class:`TeamNameMapper` (fuzzy fallback).
   - Ensure a Competition row exists for ``event['sport_title']`` and a Season
     row for ``ODDS_API_DEFAULT_SEASON_YEAR``.
   - Upsert a Match row, deduping on
     ``(season_id, home_team_id, away_team_id, match_date)``.
   - Convert bookmakers list → ``OddsDTO`` rows via the adapter helper, then
     insert into ``odds_snapshots`` using the existing dedup window.

Designed to be safe to re-run: matches upsert in place, odds snapshots dedupe
on ``(match_id, bookmaker, market_type, market_value, snapshot_at)``.

Quota notes
-----------
``ODDS_API_MAX_CALLS_PER_RUN`` caps the number of sport-key listings fetched
per invocation. The script never calls the per-event endpoint because the
listing call already includes bookmakers + markets.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from typing import Any

import structlog
from sqlalchemy import select

from src.adapters.odds_api import OddsApiAdapter
from src.config.settings import settings
from src.dto.match import MatchDTO
from src.dto.odds import OddsDTO
from src.models.competition import Competition
from src.models.match import Match
from src.models.odds_snapshot import OddsSnapshot
from src.models.season import Season
from src.utils.db import session_scope
from src.utils.logging import configure_logging
from src.utils.name_mapping import TeamNameMapper
from src.utils.validators import (
    DataValidationError,
    is_duplicate_odds_snapshot,
    validate_odds_value,
)

logger = structlog.get_logger(__name__)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--sport-keys",
        nargs="*",
        default=None,
        help="Override settings.ODDS_API_SPORT_KEYS for this run.",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch + log counts but don't write to the DB.",
    )
    return p.parse_args()


async def main_async(args: argparse.Namespace) -> int:
    if not settings.ODDS_API_KEY:
        logger.error("odds_api_key_missing", note="set ODDS_API_KEY in .env")
        return 2

    sport_keys = args.sport_keys or settings.ODDS_API_SPORT_KEYS
    if len(sport_keys) > settings.ODDS_API_MAX_CALLS_PER_RUN:
        logger.warning(
            "odds_api_quota_cap_applied",
            requested=len(sport_keys),
            cap=settings.ODDS_API_MAX_CALLS_PER_RUN,
        )
        sport_keys = sport_keys[: settings.ODDS_API_MAX_CALLS_PER_RUN]

    totals = {"events": 0, "matches_upserted": 0, "odds_inserted": 0, "odds_skipped": 0}

    async with OddsApiAdapter() as adapter:
        for sport_key in sport_keys:
            try:
                events = await adapter._fetch_sport_events(sport_key)  # type: ignore[attr-defined]
            except Exception as exc:  # noqa: BLE001 — surface any HTTP issue
                logger.error("odds_api_fetch_failed", sport_key=sport_key, error=repr(exc))
                continue

            logger.info("odds_api_sport_fetched", sport_key=sport_key, events=len(events))
            totals["events"] += len(events)

            if args.dry_run:
                continue

            for event in events:
                _ingest_event(event, sport_key=sport_key, adapter=adapter, totals=totals)

    logger.info("odds_api_pull_done", **totals)
    return 0


def _ingest_event(
    event: dict[str, Any],
    *,
    sport_key: str,
    adapter: OddsApiAdapter,
    totals: dict[str, int],
) -> None:
    match_dto = adapter._event_to_match_dto(event, sport_key=sport_key)  # type: ignore[attr-defined]
    odds_dtos = adapter._event_to_odds_dtos(event)  # type: ignore[attr-defined]

    with session_scope() as session:
        match_id = _upsert_match(session, match_dto)
        if match_id is None:
            logger.warning(
                "odds_api_event_dropped",
                external_id=match_dto.external_id,
                home=match_dto.home_team_name,
                away=match_dto.away_team_name,
                reason="team_unresolved",
            )
            return
        totals["matches_upserted"] += 1

        inserted, skipped = _insert_odds_snapshots(session, match_id, odds_dtos)
        totals["odds_inserted"] += inserted
        totals["odds_skipped"] += skipped


def _upsert_match(session, dto: MatchDTO) -> int | None:
    mapper = TeamNameMapper(session)
    home_id = mapper.resolve(dto.home_team_name, source="odds_api")
    away_id = mapper.resolve(dto.away_team_name, source="odds_api")
    if home_id is None or away_id is None:
        return None

    competition = (
        session.query(Competition)
        .filter(Competition.name == dto.competition_name)
        .one_or_none()
    )
    if competition is None:
        competition = Competition(
            name=dto.competition_name,
            competition_type="national",
            is_active=True,
        )
        session.add(competition)
        session.flush()

    year = settings.ODDS_API_DEFAULT_SEASON_YEAR or dto.season_year
    season = (
        session.query(Season)
        .filter(Season.competition_id == competition.id, Season.year == year)
        .one_or_none()
    )
    if season is None:
        season = Season(competition_id=competition.id, year=year)
        session.add(season)
        session.flush()

    existing = session.execute(
        select(Match.id).where(
            Match.season_id == season.id,
            Match.home_team_id == home_id,
            Match.away_team_id == away_id,
            Match.match_date == dto.match_date,
        )
    ).scalar()
    if existing is not None:
        return int(existing)

    match = Match(
        season_id=season.id,
        home_team_id=home_id,
        away_team_id=away_id,
        match_date=dto.match_date,
        status=dto.status,
        venue=dto.venue,
        round=dto.round,
    )
    session.add(match)
    session.flush()
    return int(match.id)


def _insert_odds_snapshots(
    session, match_id: int, dtos: list[OddsDTO]
) -> tuple[int, int]:
    inserted = 0
    skipped = 0
    for dto in dtos:
        try:
            for odds in dto.outcomes.values():
                validate_odds_value(odds)
        except DataValidationError as exc:
            logger.warning("odds_dropped_invalid", error=str(exc))
            skipped += 1
            continue

        if is_duplicate_odds_snapshot(
            session,
            match_id=match_id,
            bookmaker=dto.bookmaker,
            market_type=dto.market_type,
            market_value=dto.market_value,
            snapshot_at=dto.snapshot_at,
        ):
            skipped += 1
            continue

        snapshot = OddsSnapshot(
            match_id=match_id,
            bookmaker=dto.bookmaker,
            market_type=dto.market_type,
            market_value=dto.market_value,
            outcome_home=dto.outcomes.get("home"),
            outcome_draw=dto.outcomes.get("draw"),
            outcome_away=dto.outcomes.get("away"),
            outcome_over=dto.outcomes.get("over"),
            outcome_under=dto.outcomes.get("under"),
            outcome_yes=dto.outcomes.get("yes"),
            outcome_no=dto.outcomes.get("no"),
            snapshot_at=dto.snapshot_at,
            data_source="odds_api",
        )
        session.add(snapshot)
        inserted += 1
    return inserted, skipped


if __name__ == "__main__":
    configure_logging(json_logs=False)
    try:
        sys.exit(asyncio.run(main_async(parse_args())))
    except KeyboardInterrupt:
        logger.warning("odds_api_pull_interrupted")
        sys.exit(130)

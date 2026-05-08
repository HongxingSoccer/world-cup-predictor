"""Bookmaker-odds ingest pipeline (append-only).

Each call writes new rows to `odds_snapshots`; updates are not used because
the table is the immutable book-of-record for price movement. The dedup check
in `src.utils.validators.is_duplicate_odds_snapshot` prevents re-recording the
same quote within the configured window.
"""
from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import Insert as PGInsert
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from src.dto.odds import OddsDTO
from src.events.topics import TOPIC_ODDS_UPDATED
from src.models.match import Match
from src.models.odds_snapshot import OddsSnapshot
from src.pipelines.base import BasePipeline
from src.utils.validators import (
    DataValidationError,
    is_duplicate_odds_snapshot,
    validate_odds_value,
)

logger = structlog.get_logger(__name__)


class OddsPipeline(BasePipeline[OddsDTO]):
    """Append bookmaker odds snapshots into `odds_snapshots`."""

    task_type = "odds"
    event_type = TOPIC_ODDS_UPDATED

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        # external_id → matches.id overrides for sources without an integer
        # api_football_id. Populated via :meth:`set_match_resolution_hint`.
        self._match_id_hints: dict[str, int] = {}

    async def fetch_dtos(self, **kwargs: Any) -> list[OddsDTO]:
        match_id = kwargs.get("match_id")
        if match_id is None:
            raise ValueError("OddsPipeline.run() requires match_id=...")
        detail = await self._adapter.fetch_match_detail(match_id)
        return list(detail.odds)

    def resolve_and_map(
        self,
        session: Session,
        dtos: list[OddsDTO],
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for dto in dtos:
            try:
                for odds in dto.outcomes.values():
                    validate_odds_value(odds)
            except DataValidationError as exc:
                self._log.warning("odds_dropped_invalid", external_id=dto.match_external_id, error=str(exc))
                continue

            match_id = self._resolve_match(session, dto.match_external_id)
            if match_id is None:
                self._log.warning("odds_dropped_unresolved_match", external_id=dto.match_external_id)
                continue

            if is_duplicate_odds_snapshot(
                session,
                match_id=match_id,
                bookmaker=dto.bookmaker,
                market_type=dto.market_type,
                market_value=dto.market_value,
                snapshot_at=dto.snapshot_at,
            ):
                self._log.debug(
                    "odds_dedup_skip",
                    match_id=match_id,
                    bookmaker=dto.bookmaker,
                    market_type=dto.market_type,
                )
                continue

            rows.append(
                {
                    "match_id": match_id,
                    "bookmaker": dto.bookmaker,
                    "market_type": dto.market_type,
                    "market_value": dto.market_value,
                    "outcome_home": dto.outcomes.get("home"),
                    "outcome_draw": dto.outcomes.get("draw"),
                    "outcome_away": dto.outcomes.get("away"),
                    "outcome_over": dto.outcomes.get("over"),
                    "outcome_under": dto.outcomes.get("under"),
                    "outcome_yes": dto.outcomes.get("yes"),
                    "outcome_no": dto.outcomes.get("no"),
                    "snapshot_at": dto.snapshot_at,
                    "data_source": self._adapter.source_name,
                }
            )
        return rows

    def build_upsert(self, rows: list[dict[str, Any]]) -> PGInsert:
        # Append-only — no UNIQUE conflict to handle, but `pg_insert` is still
        # the right surface so the base class's batched executemany works.
        return pg_insert(OddsSnapshot).values(rows)

    def event_payload(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "match_id": row["match_id"],
            "bookmaker": row["bookmaker"],
            "market_type": row["market_type"],
            "market_value": row["market_value"],
            "snapshot_at": row["snapshot_at"].isoformat() if row["snapshot_at"] else None,
        }

    def event_key(self, row: dict[str, Any]) -> str:
        return f"{row['match_id']}:{row['bookmaker']}:{row['market_type']}"

    # --- Private helpers ---

    def _resolve_match(self, session: Session, external_id: str) -> int | None:
        try:
            api_id = int(external_id)
        except ValueError:
            # OddsAPI / scraper sources expose UUID-shaped ids that don't map
            # to api_football_id. Callers can stash a (home_id, away_id, date)
            # hint on the pipeline via :meth:`set_match_resolution_hint` before
            # invoking ``persist`` — see ``scripts/pull_odds_api.py``.
            hint = self._match_id_hints.get(external_id)
            return hint
        return session.execute(
            select(Match.id).where(Match.api_football_id == api_id).limit(1)
        ).scalar()

    # --- Public helper used by non-API-Football ingestion paths ---

    def set_match_resolution_hint(self, external_id: str, match_id: int) -> None:
        """Pre-register an ``external_id → matches.id`` mapping.

        Lets callers that already resolved the match (e.g. by team-name + date)
        feed odds DTOs through the standard pipeline without needing the
        adapter to expose an integer ``api_football_id``.
        """
        self._match_id_hints[external_id] = match_id

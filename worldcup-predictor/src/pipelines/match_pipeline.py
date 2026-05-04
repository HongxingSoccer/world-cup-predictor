"""Match-fixture ingest pipeline.

Pulls `MatchDTO`s from the adapter, resolves competition / season / team
references against the catalog tables, and upserts into `matches` keyed by the
adapter's external id.
"""
from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import Insert as PGInsert
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from src.dto.match import MatchDTO
from src.events.topics import TOPIC_MATCH_FINISHED, TOPIC_MATCH_UPDATED
from src.models.competition import Competition
from src.models.match import Match
from src.models.season import Season
from src.pipelines.base import BasePipeline
from src.utils.name_mapping import TeamNameMapper
from src.utils.validators import DataValidationError, validate_match_fields

logger = structlog.get_logger(__name__)


class MatchPipeline(BasePipeline[MatchDTO]):
    """Ingest fixtures + scores into `matches`."""

    task_type = "matches"
    # Default event type for non-finished rows; finished rows route to
    # TOPIC_MATCH_FINISHED via `_event_type_for_row`. Discriminating
    # match.created vs match.updated requires the xmax-based RETURNING trick
    # and is deferred to Phase 2 — for now both insert and update emit
    # match.updated, which is the safe superset.
    event_type = TOPIC_MATCH_UPDATED

    async def fetch_dtos(self, **kwargs: Any) -> list[MatchDTO]:
        season_id = kwargs.get("season_id")
        if season_id is None:
            raise ValueError("MatchPipeline.run() requires season_id=...")
        return await self._adapter.fetch_matches(season_id)

    def resolve_and_map(
        self,
        session: Session,
        dtos: list[MatchDTO],
    ) -> list[dict[str, Any]]:
        mapper = TeamNameMapper(session)
        rows: list[dict[str, Any]] = []

        for dto in dtos:
            try:
                validate_match_fields(
                    match_date=dto.match_date,
                    home_score=dto.home_score,
                    away_score=dto.away_score,
                )
            except DataValidationError as exc:
                self._log.warning("match_dropped_invalid", external_id=dto.external_id, error=str(exc))
                continue

            season_id = self._resolve_season(session, dto)
            if season_id is None:
                self._log.warning("match_dropped_unknown_season", external_id=dto.external_id)
                continue

            home_id = mapper.resolve(dto.home_team_name, self._adapter.source_name)
            away_id = mapper.resolve(dto.away_team_name, self._adapter.source_name)
            if home_id is None or away_id is None:
                self._log.warning(
                    "match_dropped_unresolved_team",
                    external_id=dto.external_id,
                    home=dto.home_team_name,
                    away=dto.away_team_name,
                )
                continue

            api_id = _maybe_int(dto.external_id)
            rows.append(
                {
                    "api_football_id": api_id,
                    "season_id": season_id,
                    "home_team_id": home_id,
                    "away_team_id": away_id,
                    "match_date": dto.match_date,
                    "venue": dto.venue,
                    "round": dto.round,
                    "status": dto.status,
                    "home_score": dto.home_score,
                    "away_score": dto.away_score,
                }
            )
        return rows

    def build_upsert(self, rows: list[dict[str, Any]]) -> PGInsert:
        # Conflict target: the partial unique index on (api_football_id) when not null.
        stmt = pg_insert(Match).values(rows)
        update_cols = {
            col.name: stmt.excluded[col.name]
            for col in Match.__table__.columns
            if col.name not in {"id", "created_at", "api_football_id"}
        }
        return stmt.on_conflict_do_update(
            index_elements=["api_football_id"],
            index_where=Match.api_football_id.is_not(None),
            set_=update_cols,
        )

    def event_payload(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "external_id": row["api_football_id"],
            "season_id": row["season_id"],
            "home_team_id": row["home_team_id"],
            "away_team_id": row["away_team_id"],
            "match_date": row["match_date"].isoformat() if row["match_date"] else None,
            "status": row["status"],
        }

    def event_key(self, row: dict[str, Any]) -> str:
        return str(row["api_football_id"] or f"{row['home_team_id']}-{row['away_team_id']}-{row['match_date']}")

    def _event_type_for_row(self, row: dict[str, Any]) -> str:
        return TOPIC_MATCH_FINISHED if row.get("status") == "finished" else TOPIC_MATCH_UPDATED

    # --- Private helpers ---

    def _resolve_season(self, session: Session, dto: MatchDTO) -> int | None:
        stmt = (
            select(Season.id)
            .join(Competition, Competition.id == Season.competition_id)
            .where(Competition.name == dto.competition_name, Season.year == dto.season_year)
            .limit(1)
        )
        row = session.execute(stmt).first()
        return int(row[0]) if row else None


def _maybe_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None

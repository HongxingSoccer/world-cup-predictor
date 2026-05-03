"""Player master-data ingest pipeline.

Ingests `PlayerDTO`s and upserts into `players`, resolving current-team /
national-team external ids via `teams.api_football_id`. Single-match player
stats and valuations live in their own pipelines (see `stats_pipeline` and
forthcoming valuation/injury pipelines).
"""
from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import Insert as PGInsert
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from src.dto.player import PlayerDTO
# Player events don't have a dedicated topic in Phase 1's event taxonomy,
# so player updates go under match.updated as a generic "ingest progressed"
# signal until Phase 2 introduces a player.* topic family.
from src.events.topics import TOPIC_MATCH_UPDATED
from src.models.player import Player
from src.models.team import Team
from src.pipelines.base import BasePipeline
from src.utils.validators import DataValidationError, validate_player_market_value

logger = structlog.get_logger(__name__)


class PlayerPipeline(BasePipeline[PlayerDTO]):
    """Upsert player master records into `players`."""

    task_type = "players"
    event_type = TOPIC_MATCH_UPDATED

    async def fetch_dtos(self, **kwargs: Any) -> list[PlayerDTO]:
        # Different adapters expose different scopes (per-team / per-match);
        # the concrete adapter decides what `kwargs` are accepted. We just pass
        # them through.
        method_name = kwargs.pop("adapter_method", "fetch_players")
        method = getattr(self._adapter, method_name, None)
        if method is None:
            raise AttributeError(
                f"Adapter {self._adapter.source_name} has no method {method_name!r}"
            )
        return await method(**kwargs)

    def resolve_and_map(
        self,
        session: Session,
        dtos: list[PlayerDTO],
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for dto in dtos:
            try:
                validate_player_market_value(dto.market_value_eur)
            except DataValidationError as exc:
                self._log.warning("player_dropped_invalid", external_id=dto.external_id, error=str(exc))
                continue

            api_id = _maybe_int(dto.external_id)
            current_team_id = self._resolve_team(session, dto.current_team_external_id)
            national_team_id = self._resolve_team(session, dto.national_team_external_id)

            rows.append(
                {
                    "api_football_id": api_id,
                    "name": dto.name,
                    "nationality": dto.nationality,
                    "date_of_birth": dto.date_of_birth,
                    "position": dto.position,
                    "current_team_id": current_team_id,
                    "national_team_id": national_team_id,
                    "market_value_eur": dto.market_value_eur,
                    "photo_url": dto.photo_url,
                }
            )
        return rows

    def build_upsert(self, rows: list[dict[str, Any]]) -> PGInsert:
        stmt = pg_insert(Player).values(rows)
        update_cols = {
            col.name: stmt.excluded[col.name]
            for col in Player.__table__.columns
            if col.name not in {"id", "created_at", "api_football_id"}
        }
        return stmt.on_conflict_do_update(
            index_elements=["api_football_id"],
            set_=update_cols,
        )

    def event_payload(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "external_id": row["api_football_id"],
            "name": row["name"],
            "current_team_id": row["current_team_id"],
            "national_team_id": row["national_team_id"],
        }

    def event_key(self, row: dict[str, Any]) -> str:
        return str(row["api_football_id"] or row["name"])

    # --- Private helpers ---

    def _resolve_team(self, session: Session, external_id: str | None) -> int | None:
        if external_id is None:
            return None
        api_id = _maybe_int(external_id)
        if api_id is None:
            return None
        return session.execute(
            select(Team.id).where(Team.api_football_id == api_id).limit(1)
        ).scalar()


def _maybe_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None

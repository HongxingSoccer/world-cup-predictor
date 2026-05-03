"""Match-stats ingest pipeline.

Consumes (home, away) `MatchStatsDTO` pairs from a single match's detail
payload and upserts into `match_stats` (one row per (match, team)).
"""
from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import Insert as PGInsert
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from src.dto.stats import MatchDetailDTO, MatchStatsDTO
from src.events.topics import TOPIC_MATCH_UPDATED
from src.models.match import Match
from src.models.match_stats import MatchStats
from src.models.team import Team
from src.pipelines.base import BasePipeline
from src.utils.validators import (
    DataValidationError,
    validate_possession_pair,
    validate_team_stats,
)

logger = structlog.get_logger(__name__)


class StatsPipeline(BasePipeline[MatchStatsDTO]):
    """Ingest per-team aggregate stats into `match_stats`."""

    task_type = "match_stats"
    # Stats arrive after the match is in our DB; we publish under match.updated
    # so consumers tracking match-level state see the new fields without
    # subscribing to a stats-specific topic.
    event_type = TOPIC_MATCH_UPDATED

    async def fetch_dtos(self, **kwargs: Any) -> list[MatchStatsDTO]:
        match_id = kwargs.get("match_id")
        if match_id is None:
            raise ValueError("StatsPipeline.run() requires match_id=...")
        detail: MatchDetailDTO = await self._adapter.fetch_match_detail(match_id)

        try:
            validate_possession_pair(
                detail.home_stats.possession if detail.home_stats else None,
                detail.away_stats.possession if detail.away_stats else None,
            )
        except DataValidationError as exc:
            self._log.warning("possession_pair_invalid", match_id=match_id, error=str(exc))

        return [s for s in (detail.home_stats, detail.away_stats) if s is not None]

    def resolve_and_map(
        self,
        session: Session,
        dtos: list[MatchStatsDTO],
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for dto in dtos:
            try:
                validate_team_stats(xg=dto.xg, possession=dto.possession)
            except DataValidationError as exc:
                self._log.warning("stats_dropped_invalid", external_id=dto.match_external_id, error=str(exc))
                continue

            match_id = self._resolve_match(session, dto.match_external_id)
            team_id = self._resolve_team(session, dto.team_external_id)
            if match_id is None or team_id is None:
                self._log.warning(
                    "stats_dropped_unresolved",
                    match_external_id=dto.match_external_id,
                    team_external_id=dto.team_external_id,
                )
                continue

            rows.append(
                {
                    "match_id": match_id,
                    "team_id": team_id,
                    "is_home": dto.is_home,
                    "possession": dto.possession,
                    "shots": dto.shots,
                    "shots_on_target": dto.shots_on_target,
                    "xg": dto.xg,
                    "xg_against": dto.xg_against,
                    "passes": dto.passes,
                    "pass_accuracy": dto.pass_accuracy,
                    "corners": dto.corners,
                    "fouls": dto.fouls,
                    "yellow_cards": dto.yellow_cards,
                    "red_cards": dto.red_cards,
                    "offsides": dto.offsides,
                    "tackles": dto.tackles,
                    "interceptions": dto.interceptions,
                    "saves": dto.saves,
                    "data_source": dto.data_source,
                }
            )
        return rows

    def build_upsert(self, rows: list[dict[str, Any]]) -> PGInsert:
        stmt = pg_insert(MatchStats).values(rows)
        update_cols = {
            col.name: stmt.excluded[col.name]
            for col in MatchStats.__table__.columns
            if col.name not in {"id", "created_at", "match_id", "team_id"}
        }
        return stmt.on_conflict_do_update(
            constraint="uq_match_stats_match_team",
            set_=update_cols,
        )

    def event_payload(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "match_id": row["match_id"],
            "team_id": row["team_id"],
            "is_home": row["is_home"],
            "data_source": row["data_source"],
        }

    def event_key(self, row: dict[str, Any]) -> str:
        return f"{row['match_id']}:{row['team_id']}"

    # --- Private helpers ---

    def _resolve_match(self, session: Session, external_id: str) -> int | None:
        api_id = _maybe_int(external_id)
        if api_id is None:
            return None
        return session.execute(
            select(Match.id).where(Match.api_football_id == api_id).limit(1)
        ).scalar()

    def _resolve_team(self, session: Session, external_id: str) -> int | None:
        # Stats DTOs use the same source as the match — the upstream adapter
        # already gave us a numeric id, so we look up via teams.api_football_id.
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

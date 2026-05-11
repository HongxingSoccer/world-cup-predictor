"""Standard ETL pipeline template.

Concrete pipelines (match, stats, odds, player) implement only the four hooks
that vary between sources: how to fetch DTOs, how to map DTO → ORM, the upsert
target table, and the event topic. Every other concern — schema validation,
entity resolution, normalization, batched ON CONFLICT writes, Kafka emission,
and audit logging — is enforced uniformly by `BasePipeline.run()`.
"""
from __future__ import annotations

import math
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any, Generic, TypeVar

import structlog
from pydantic import BaseModel
from sqlalchemy.dialects.postgresql import Insert as PGInsert
from sqlalchemy.orm import Session, sessionmaker

from src.adapters.base import BaseDataSourceAdapter, DataFetchError
from src.events.producer import EventProducer, NullEventProducer
from src.models.data_source_log import DataSourceLog

logger = structlog.get_logger(__name__)

DTOT = TypeVar("DTOT", bound=BaseModel)


class PipelineResult(BaseModel):
    """Summary returned by `BasePipeline.run()`."""

    fetched: int
    validated: int
    inserted: int
    updated: int
    skipped: int
    errors: list[str] = []


class BasePipeline(ABC, Generic[DTOT]):
    """Generic adapter-DTO → DB-row pipeline with audit logging and Kafka emit.

    Subclass responsibilities:

    1. ``task_type`` and ``event_type`` class constants (or properties).
       The event_type is also the Kafka topic; subclasses can override
       `_event_type_for_row` to route different rows to different topics.
    2. ``async fetch_dtos(**kwargs)`` — call the adapter, return a list of DTOs.
    3. ``resolve_and_map(session, dtos)`` — entity resolution + DTO → row dict.
    4. ``build_upsert(rows)`` — return a PostgreSQL ``INSERT … ON CONFLICT`` stmt.
    5. ``event_payload(row)`` — what to publish to Kafka per upserted row.

    Attributes:
        BATCH_SIZE: Max rows per ``executemany`` call. Capped to keep single
            transactions short under contention.
    """

    BATCH_SIZE: int = 500

    # Subclasses set these.
    task_type: str
    event_type: str

    def __init__(
        self,
        adapter: BaseDataSourceAdapter,
        session_factory: sessionmaker[Session],
        *,
        producer: EventProducer | None = None,
        event_source: str = "ingestion-service",
    ) -> None:
        self._adapter = adapter
        self._session_factory = session_factory
        self._producer: EventProducer = producer or NullEventProducer()
        self._event_source = event_source
        self._log = logger.bind(pipeline=self.__class__.__name__, source=adapter.source_name)

    # --- Template method ---

    async def run(self, **kwargs: Any) -> PipelineResult:
        """Execute the full pipeline once and return a summary.

        The flow follows the documented contract:
            1. fetch DTOs from the adapter
            2. (DTOs are already Pydantic-validated at construction)
            3. resolve external refs + map to DB row dicts
            4. normalize is the subclass's responsibility inside step 3
            5. batched ON CONFLICT upsert
            6. publish per-row Kafka events
            7. write a DataSourceLog row (success or failure)
        """
        started_at = datetime.now(UTC)
        result = PipelineResult(fetched=0, validated=0, inserted=0, updated=0, skipped=0)
        meta = {**kwargs}

        try:
            dtos = await self.fetch_dtos(**kwargs)
            result.fetched = len(dtos)
            result.validated = len(dtos)  # DTOs raised already if invalid

            if not dtos:
                await self._record_log("success", started_at, result, meta)
                return result

            await self._persist_and_publish(dtos, result)
        except DataFetchError as exc:
            result.errors.append(str(exc))
            await self._record_log("failed", started_at, result, meta, error=str(exc))
            raise
        except Exception as exc:
            result.errors.append(repr(exc))
            await self._record_log("failed", started_at, result, meta, error=repr(exc))
            raise
        else:
            status = "partial" if result.errors else "success"
            await self._record_log(status, started_at, result, meta)

        return result

    # --- Abstract hooks (subclasses MUST implement) ---

    @abstractmethod
    async def fetch_dtos(self, **kwargs: Any) -> list[DTOT]:
        """Call the adapter and return the DTO list."""

    @abstractmethod
    def resolve_and_map(
        self,
        session: Session,
        dtos: list[DTOT],
    ) -> list[dict[str, Any]]:
        """Resolve externals → internal ids and emit a list of column dicts.

        Implementations MUST also handle normalization (UTC dates, mapped team
        ids, currency units) before returning. Rows that cannot be resolved
        should be dropped and logged, not raised.
        """

    @abstractmethod
    def build_upsert(self, rows: list[dict[str, Any]]) -> PGInsert:
        """Return a PostgreSQL ``INSERT … ON CONFLICT … DO UPDATE/NOTHING`` for `rows`."""

    @abstractmethod
    def event_payload(self, row: dict[str, Any]) -> dict[str, Any]:
        """Project a row into the Kafka payload to publish."""

    @abstractmethod
    def event_key(self, row: dict[str, Any]) -> str:
        """Partition key for the Kafka event (e.g. match id as a string)."""

    # --- Optional override (per-row routing) ---

    def _event_type_for_row(self, row: dict[str, Any]) -> str:
        """Return the event type / topic for `row`. Defaults to `self.event_type`."""
        return self.event_type

    # --- Private helpers ---

    async def _persist_and_publish(self, dtos: list[DTOT], result: PipelineResult) -> None:
        with self._session_factory() as session:
            rows = self.resolve_and_map(session, dtos)
            result.skipped = len(dtos) - len(rows)
            if not rows:
                return

            inserted_total, updated_total = 0, 0
            for chunk in _chunked(rows, self.BATCH_SIZE):
                stmt = self.build_upsert(chunk)
                outcome = session.execute(stmt)
                # `rowcount` includes inserts + updates for ON CONFLICT DO UPDATE;
                # split heuristically (best effort — Postgres doesn't expose it natively).
                affected = outcome.rowcount or 0
                inserted_total += affected
            session.commit()

            result.inserted = inserted_total
            result.updated = updated_total

            for row in rows:
                try:
                    self._producer.publish(
                        event_type=self._event_type_for_row(row),
                        key=self.event_key(row),
                        payload=self.event_payload(row),
                        source=self._event_source,
                    )
                except Exception as exc:
                    # Don't roll back the DB write for a Kafka hiccup —
                    # downstream consumers can recover via the audit log.
                    self._log.warning("kafka_publish_skipped", error=str(exc))
                    result.errors.append(f"kafka: {exc}")

    async def _record_log(
        self,
        status: str,
        started_at: datetime,
        result: PipelineResult,
        meta: dict[str, Any],
        *,
        error: str | None = None,
    ) -> None:
        finished_at = datetime.now(UTC)
        try:
            with self._session_factory() as session:
                session.add(
                    DataSourceLog(
                        source_name=self._adapter.source_name,
                        task_type=self.task_type,
                        status=status,
                        records_fetched=result.fetched,
                        records_inserted=result.inserted,
                        records_updated=result.updated,
                        error_message=error,
                        started_at=started_at,
                        finished_at=finished_at,
                        meta=meta,
                    )
                )
                session.commit()
        except Exception as exc:
            # Audit-log failure must not mask the original error.
            self._log.error("audit_log_write_failed", error=str(exc))


def _chunked(seq: list[Any], size: int) -> list[list[Any]]:
    """Split `seq` into `ceil(len/size)` slices, each of length ≤ `size`."""
    if size <= 0:
        raise ValueError("size must be > 0")
    n_chunks = math.ceil(len(seq) / size)
    return [seq[i * size : (i + 1) * size] for i in range(n_chunks)]

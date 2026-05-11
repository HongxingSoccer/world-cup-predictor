"""data_source_logs — audit trail for every ingest run.

Each row covers a single (source, task) execution. The free-form `meta`
JSONB stores task-specific context (request params, page counts, rate-limit
state, etc.). Used by ops dashboards and by the scheduler to back off after
repeated failures.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, Index, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class DataSourceLog(Base):
    __tablename__ = "data_source_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # 'api_football' | 'transfermarkt' | 'fbref' | 'odds_api' | 'understat' | ...
    source_name: Mapped[str] = mapped_column(String(50), nullable=False)
    # 'fixtures' | 'lineups' | 'odds' | 'valuations' | 'injuries' | ...
    task_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # 'success' | 'partial' | 'failed' | 'skipped' | 'running'
    status: Mapped[str] = mapped_column(String(20), nullable=False)

    records_fetched: Mapped[int | None] = mapped_column(Integer, nullable=True)
    records_inserted: Mapped[int | None] = mapped_column(Integer, nullable=True)
    records_updated: Mapped[int | None] = mapped_column(Integer, nullable=True)

    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    meta: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("idx_logs_source_time", "source_name", text("started_at DESC")),
        Index("idx_logs_status", "status"),
    )

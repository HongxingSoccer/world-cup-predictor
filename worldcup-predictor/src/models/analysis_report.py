"""analysis_reports — AI-generated Chinese match analysis reports (Phase 4).

Schema follows ``docs/design/06_Phase4_ModelEvolution.md §4.5``:
    - One *published* report per ``match_id`` (partial unique index).
    - Both Markdown and rendered HTML are stored; ``summary`` powers
      OG previews and notification bodies.
    - ``model_used`` records the LLM (e.g. ``claude-sonnet-4-20250514``).
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class AnalysisReport(Base):
    __tablename__ = "analysis_reports"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    match_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    prediction_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content_md: Mapped[str] = mapped_column(Text, nullable=False)
    content_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str] = mapped_column(String(500), nullable=False)
    model_used: Mapped[str] = mapped_column(String(30), nullable=False)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="draft")
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index(
            "uq_reports_match_published",
            "match_id",
            unique=True,
            postgresql_where=text("status = 'published'"),
        ),
        Index("idx_reports_published", "published_at"),
    )

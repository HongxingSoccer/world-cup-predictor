"""matches — core fact table for fixtures and results.

Every other match-level table (stats, lineups, odds, elo) hangs off this one.
The `data_completeness` field is a 0–100 score maintained by the ingest
pipelines; downstream models should filter on it for training quality.
"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .season import Season


class Match(Base, TimestampMixin):
    __tablename__ = "matches"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    api_football_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    season_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("seasons.id", ondelete="RESTRICT"), nullable=False
    )
    home_team_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("teams.id", ondelete="RESTRICT"), nullable=False
    )
    away_team_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("teams.id", ondelete="RESTRICT"), nullable=False
    )

    match_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    venue: Mapped[str | None] = mapped_column(String(200), nullable=True)
    round: Mapped[str | None] = mapped_column(String(50), nullable=True)

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="scheduled", server_default="scheduled"
    )

    home_score: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    away_score: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    home_score_ht: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    away_score_ht: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)

    referee: Mapped[str | None] = mapped_column(String(100), nullable=True)
    attendance: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # 0..100 — completeness score across required attributes (stats, lineups, odds, …).
    data_completeness: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=0, server_default="0"
    )

    season: Mapped[Season] = relationship(back_populates="matches")

    __table_args__ = (
        CheckConstraint(
            "status IN ('scheduled','live','finished','postponed','cancelled')",
            name="ck_matches_status",
        ),
        Index(
            "uq_matches_api_football_id",
            "api_football_id",
            unique=True,
            postgresql_where=text("api_football_id IS NOT NULL"),
        ),
        Index("idx_matches_date", text("match_date DESC")),
        Index("idx_matches_season", "season_id"),
        Index("idx_matches_teams", "home_team_id", "away_team_id"),
        Index("idx_matches_status", "status"),
    )

"""match_stats — per-team aggregated stats for a single match.

One row per (match, team), so a finished match should produce exactly two rows
(home + away). The `data_source` column records which provider supplied the
numbers, so reconciliation can compare API-Football vs FBref vs scraped values.
"""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    ForeignKey,
    Index,
    Numeric,
    SmallInteger,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class MatchStats(Base, TimestampMixin):
    __tablename__ = "match_stats"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    match_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("matches.id", ondelete="CASCADE"), nullable=False
    )
    team_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("teams.id", ondelete="RESTRICT"), nullable=False
    )
    is_home: Mapped[bool] = mapped_column(Boolean, nullable=False)

    possession: Mapped[Decimal | None] = mapped_column(Numeric(4, 1), nullable=True)
    shots: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    shots_on_target: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    xg: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    xg_against: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    passes: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    pass_accuracy: Mapped[Decimal | None] = mapped_column(Numeric(4, 1), nullable=True)
    corners: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    fouls: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    yellow_cards: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    red_cards: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    offsides: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    tackles: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    interceptions: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    saves: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)

    # 'api_football' | 'fbref' | 'understat' | 'scraper:<site>'
    data_source: Mapped[str] = mapped_column(String(30), nullable=False)

    __table_args__ = (
        UniqueConstraint("match_id", "team_id", name="uq_match_stats_match_team"),
        Index("idx_match_stats_team", "team_id", "match_id"),
    )

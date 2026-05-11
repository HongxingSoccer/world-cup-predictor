"""elo_ratings — point-in-time Elo (or related) rating snapshots per team.

`match_id` is set when the rating change is the result of a specific match;
NULL is allowed for periodic re-baselines or initial seeding rows.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class EloRating(Base):
    __tablename__ = "elo_ratings"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    team_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False
    )
    match_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("matches.id", ondelete="SET NULL"), nullable=True
    )

    rating: Mapped[Decimal] = mapped_column(
        Numeric(7, 2), nullable=False, default=Decimal("1500.00"), server_default="1500.00"
    )
    rating_change: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    rated_at: Mapped[date] = mapped_column(Date, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("idx_elo_team_date", "team_id", text("rated_at DESC")),
        Index("idx_elo_match", "match_id"),
    )

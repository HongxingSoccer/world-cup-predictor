"""h2h_records — denormalized head-to-head aggregates for fast lookup.

Convention: writers MUST canonicalize the pair so `team_a_id < team_b_id`,
i.e. the smaller id is always team_a. The CHECK constraint enforces this so
duplicates with reversed pairs cannot exist.
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    SmallInteger,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class H2HRecord(Base):
    __tablename__ = "h2h_records"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    team_a_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False
    )
    team_b_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False
    )

    total_matches: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0, server_default="0")
    team_a_wins: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0, server_default="0")
    team_b_wins: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0, server_default="0")
    draws: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0, server_default="0")
    team_a_goals: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0, server_default="0")
    team_b_goals: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0, server_default="0")

    last_match_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        UniqueConstraint("team_a_id", "team_b_id", name="uq_h2h_pair"),
        CheckConstraint("team_a_id < team_b_id", name="ck_h2h_canonical_order"),
    )

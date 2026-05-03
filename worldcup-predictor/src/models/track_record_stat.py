"""track_record_stats — denormalised aggregates for the public scoreboard.

A single row per `(stat_type, period)` combination; the settlement task
recomputes hit-rate / ROI / streaks and upserts on the unique key. Stored as
its own table (rather than a view) so the public ROI page can serve from a
warm Redis read-through cache without scanning thousands of result rows.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    DateTime,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class TrackRecordStat(Base):
    __tablename__ = "track_record_stats"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # 'overall' | '1x2' | 'score' | 'ou25' | 'btts' | 'positive_ev'
    stat_type: Mapped[str] = mapped_column(String(30), nullable=False)
    # 'all_time' | 'last_30d' | 'last_7d' | 'worldcup'
    period: Mapped[str] = mapped_column(String(20), nullable=False)

    total_predictions: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    hits: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    hit_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 4), nullable=False, default=Decimal("0"), server_default="0"
    )
    total_pnl_units: Mapped[Decimal] = mapped_column(
        Numeric(10, 4), nullable=False, default=Decimal("0"), server_default="0"
    )
    roi: Mapped[Decimal] = mapped_column(
        Numeric(6, 4), nullable=False, default=Decimal("0"), server_default="0"
    )

    # Positive = winning streak, negative = losing streak.
    current_streak: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    best_streak: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        UniqueConstraint("stat_type", "period", name="uq_track_stats_type_period"),
    )

"""player_valuations — historical market-value snapshots (mostly Transfermarkt).

Time-series of (player, date) → EUR. Used as a feature input for player
strength and squad-quality models.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class PlayerValuation(Base):
    __tablename__ = "player_valuations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    player_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("players.id", ondelete="CASCADE"), nullable=False
    )
    team_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("teams.id", ondelete="SET NULL"), nullable=True
    )

    value_date: Mapped[date] = mapped_column(Date, nullable=False)
    market_value_eur: Mapped[int] = mapped_column(BigInteger, nullable=False)

    data_source: Mapped[str] = mapped_column(
        String(30), nullable=False, default="transfermarkt", server_default="transfermarkt"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("player_id", "value_date", name="uq_valuations_player_date"),
        Index("idx_valuations_date", text("value_date DESC")),
    )

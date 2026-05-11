"""injuries — current and historical player injuries / unavailability.

Rows stay in the table after recovery (`is_active=false`, `actual_return` set)
to support availability-history features.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import BigInteger, Boolean, Date, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class Injury(Base, TimestampMixin):
    __tablename__ = "injuries"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    player_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("players.id", ondelete="CASCADE"), nullable=False
    )
    team_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("teams.id", ondelete="SET NULL"), nullable=True
    )

    injury_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # 'minor' | 'moderate' | 'major' | 'season-ending'
    severity: Mapped[str | None] = mapped_column(String(20), nullable=True)

    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    expected_return: Mapped[date | None] = mapped_column(Date, nullable=True)
    actual_return: Mapped[date | None] = mapped_column(Date, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")

    data_source: Mapped[str] = mapped_column(
        String(30), nullable=False, default="transfermarkt", server_default="transfermarkt"
    )

    __table_args__ = (
        Index("idx_injuries_player_active", "player_id", "is_active"),
        Index("idx_injuries_team_active", "team_id", "is_active"),
    )

"""players — player master data with external system ids and current club / national team."""
from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy import BigInteger, Date, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class Player(Base, TimestampMixin):
    __tablename__ = "players"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # External ids
    api_football_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    transfermarkt_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    fbref_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    name_zh: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    nationality: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    date_of_birth: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    # 'GK' | 'DF' | 'MF' | 'FW' (or sub-positions like 'CB','LB','CM','ST'...)
    position: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)

    # Club affiliation and (separately) national-team affiliation. Both reference teams.
    current_team_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("teams.id", ondelete="SET NULL"), nullable=True
    )
    national_team_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("teams.id", ondelete="SET NULL"), nullable=True
    )

    market_value_eur: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    market_value_updated: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    photo_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index(
            "uq_players_api_football_id",
            "api_football_id",
            unique=True,
            postgresql_where=text("api_football_id IS NOT NULL"),
        ),
        Index("idx_players_team", "current_team_id"),
        Index("idx_players_nationality", "nationality"),
    )

"""competitions — top-level competition / tournament catalog.

One row per competition (e.g. "FIFA World Cup", "UEFA Euro", "Premier League").
Distinguishes national-team competitions from club competitions via `competition_type`,
and stores the optional API-Football foreign id used by ingest jobs.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .season import Season


class Competition(Base, TimestampMixin):
    __tablename__ = "competitions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    api_football_id: Mapped[int | None] = mapped_column(Integer, unique=True, nullable=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    name_zh: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # 'national' | 'club' | 'continental' | 'friendly' (kept open as VARCHAR per schema)
    competition_type: Mapped[str] = mapped_column(String(20), nullable=False)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    logo_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")

    seasons: Mapped[list[Season]] = relationship(
        back_populates="competition", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_competitions_type_country", "competition_type", "country"),
    )

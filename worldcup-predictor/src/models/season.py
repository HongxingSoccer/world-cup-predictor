"""seasons — one row per (competition, year). Hosts the matches calendar."""
from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import BigInteger, Boolean, Date, ForeignKey, SmallInteger, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .competition import Competition
    from .match import Match


class Season(Base, TimestampMixin):
    __tablename__ = "seasons"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    competition_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("competitions.id", ondelete="CASCADE"), nullable=False
    )
    year: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")

    competition: Mapped["Competition"] = relationship(back_populates="seasons")
    matches: Mapped[List["Match"]] = relationship(
        back_populates="season", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("competition_id", "year", name="uq_seasons_competition_year"),
    )

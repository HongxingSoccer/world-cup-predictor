"""teams — clubs and national teams.

External ids from API-Football, Transfermarkt and FBref are stored side-by-side
so the entity-resolution pipeline can map any of them to a single canonical row.
The `api_football_id` uniqueness is enforced as a partial index (NULLs allowed).
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import BigInteger, Date, Index, Integer, SmallInteger, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class Team(Base, TimestampMixin):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # External system ids (any may be NULL until resolution links them).
    api_football_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    transfermarkt_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    fbref_id: Mapped[str | None] = mapped_column(String(50), nullable=True)

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    name_zh: Mapped[str | None] = mapped_column(String(200), nullable=True)
    short_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # 'national' | 'club'
    team_type: Mapped[str] = mapped_column(String(20), nullable=False)
    logo_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    fifa_ranking: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    fifa_ranking_updated: Mapped[date | None] = mapped_column(Date, nullable=True)
    # 'UEFA' | 'CONMEBOL' | 'CONCACAF' | 'CAF' | 'AFC' | 'OFC'
    confederation: Mapped[str | None] = mapped_column(String(20), nullable=True)

    __table_args__ = (
        # Partial unique index — only enforce uniqueness when the external id is present.
        Index(
            "uq_teams_api_football_id",
            "api_football_id",
            unique=True,
            postgresql_where=text("api_football_id IS NOT NULL"),
        ),
        Index("idx_teams_name", "name"),
        Index("idx_teams_country_type", "country", "team_type"),
    )

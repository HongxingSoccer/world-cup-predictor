"""player_stats — per-player single-match performance.

Box-score style stats keyed by (match, player). xG/xA when the source provides
shot-level data (FBref/Understat); otherwise NULL.
"""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    ForeignKey,
    Index,
    Numeric,
    SmallInteger,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class PlayerStats(Base):
    __tablename__ = "player_stats"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    match_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("matches.id", ondelete="CASCADE"), nullable=False
    )
    player_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("players.id", ondelete="RESTRICT"), nullable=False
    )
    team_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("teams.id", ondelete="RESTRICT"), nullable=False
    )

    goals: Mapped[int | None] = mapped_column(SmallInteger, default=0, server_default="0")
    assists: Mapped[int | None] = mapped_column(SmallInteger, default=0, server_default="0")
    xg: Mapped[Decimal | None] = mapped_column(Numeric(4, 2), nullable=True)
    xa: Mapped[Decimal | None] = mapped_column(Numeric(4, 2), nullable=True)
    shots: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    key_passes: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    tackles: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    interceptions: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    saves: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    yellow_cards: Mapped[int | None] = mapped_column(SmallInteger, default=0, server_default="0")
    red_cards: Mapped[int | None] = mapped_column(SmallInteger, default=0, server_default="0")

    data_source: Mapped[str] = mapped_column(String(30), nullable=False)

    __table_args__ = (
        UniqueConstraint("match_id", "player_id", name="uq_player_stats_match_player"),
        Index("idx_player_stats_player", "player_id"),
        Index("idx_player_stats_team_match", "team_id", "match_id"),
    )

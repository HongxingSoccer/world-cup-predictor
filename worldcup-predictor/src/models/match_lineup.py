"""match_lineups — starting XI + substitutes per match per team.

One row per player-appearance in a match. `is_starter=True` for the XI;
substitutes are inserted with `is_starter=False` and may have non-null
`sub_in_minute` / `sub_out_minute`.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

from sqlalchemy import BigInteger, Boolean, ForeignKey, Index, Numeric, SmallInteger, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class MatchLineup(Base):
    __tablename__ = "match_lineups"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    match_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("matches.id", ondelete="CASCADE"), nullable=False
    )
    team_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("teams.id", ondelete="RESTRICT"), nullable=False
    )
    player_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("players.id", ondelete="RESTRICT"), nullable=False
    )

    is_starter: Mapped[bool] = mapped_column(Boolean, nullable=False)
    position: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    jersey_number: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)
    minutes_played: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)
    sub_in_minute: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)
    sub_out_minute: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)
    rating: Mapped[Optional[Decimal]] = mapped_column(Numeric(3, 1), nullable=True)

    __table_args__ = (
        UniqueConstraint("match_id", "team_id", "player_id", name="uq_lineups_match_team_player"),
        Index("idx_lineups_player", "player_id"),
    )

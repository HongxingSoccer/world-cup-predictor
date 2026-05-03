"""odds_snapshots — append-only book-of-record for bookmaker odds.

Each row is a snapshot of a single market (1X2, OU, BTTS, …) at a single time
for a single bookmaker, so the table grows quickly. Never UPDATE — append a
new snapshot whenever odds move.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class OddsSnapshot(Base):
    __tablename__ = "odds_snapshots"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    match_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("matches.id", ondelete="CASCADE"), nullable=False
    )

    bookmaker: Mapped[str] = mapped_column(String(50), nullable=False)
    # '1x2' | 'over_under' | 'btts' | 'asian_handicap' | 'correct_score' ...
    market_type: Mapped[str] = mapped_column(String(30), nullable=False)
    # e.g. line for OU/AH ("2.5", "-1.5") or correct-score "2-1"; NULL for 1x2/btts
    market_value: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # 1x2 outcomes
    outcome_home: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 3), nullable=True)
    outcome_draw: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 3), nullable=True)
    outcome_away: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 3), nullable=True)
    # Over/Under
    outcome_over: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 3), nullable=True)
    outcome_under: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 3), nullable=True)
    # BTTS / Yes-No markets
    outcome_yes: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 3), nullable=True)
    outcome_no: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 3), nullable=True)

    snapshot_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    data_source: Mapped[str] = mapped_column(String(30), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index(
            "idx_odds_match_market",
            "match_id",
            "market_type",
            text("snapshot_at DESC"),
        ),
        Index("idx_odds_snapshot_time", text("snapshot_at DESC")),
    )

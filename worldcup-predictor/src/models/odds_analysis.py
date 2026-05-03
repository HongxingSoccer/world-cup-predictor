"""odds_analysis — per-outcome value signals computed from a `Prediction` and `OddsSnapshot`.

For each match × market × outcome combination we compare the model's
probability against the best available bookmaker odds (devigged →
`implied_prob`), compute EV / edge, and label the result with a 0-3
`signal_level` (0 = no edge, 3 = strong). Front-end and notification
services subscribe to rows where `signal_level >= 1`.

Append-only by convention; rows for a given (match, model, market, outcome)
collide on no UNIQUE constraint, but the analysis pipeline writes a single
row per analysis run so duplicates are not expected in normal operation.
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
    SmallInteger,
    String,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class OddsAnalysis(Base):
    __tablename__ = "odds_analysis"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    match_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("matches.id", ondelete="CASCADE"), nullable=False
    )
    prediction_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("predictions.id", ondelete="RESTRICT"), nullable=False
    )

    # '1x2' | 'over_under' | 'btts' | 'asian_handicap'
    market_type: Mapped[str] = mapped_column(String(30), nullable=False)
    market_value: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    # 'home' | 'draw' | 'away' | 'over' | 'under' | 'yes' | 'no'
    outcome: Mapped[str] = mapped_column(String(20), nullable=False)

    model_prob: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    best_odds: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False)
    best_bookmaker: Mapped[str] = mapped_column(String(50), nullable=False)
    # Implied probability after vig removal (de-vigged across the market basket).
    implied_prob: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)

    ev: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False)
    edge: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    # 0=no signal, 1=⭐, 2=⭐⭐, 3=⭐⭐⭐ (thresholds in the analyzer service).
    signal_level: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=0, server_default="0"
    )

    analyzed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("idx_odds_analysis_match", "match_id"),
        Index(
            "idx_odds_analysis_signal",
            text("signal_level DESC"),
            text("analyzed_at DESC"),
        ),
        Index("idx_odds_analysis_market", "market_type"),
    )

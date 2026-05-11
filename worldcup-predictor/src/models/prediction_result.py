"""prediction_results — post-match scorecard for every published prediction.

Created by a settlement task that fires once a match enters status='finished'.
Joins the immutable prediction (`predictions`) against the actual scoreline
and the highest-EV outcome from `odds_analysis`, then records hit/miss
booleans + per-unit P&L. Aggregates feed `track_record_stats`.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    SmallInteger,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class PredictionResult(Base):
    __tablename__ = "prediction_results"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    prediction_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("predictions.id", ondelete="RESTRICT"), nullable=False
    )
    match_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("matches.id", ondelete="RESTRICT"), nullable=False
    )

    actual_home_score: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    actual_away_score: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    result_1x2_hit: Mapped[bool] = mapped_column(Boolean, nullable=False)
    # Top-10 score-line hit.
    result_score_hit: Mapped[bool] = mapped_column(Boolean, nullable=False)
    result_ou25_hit: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    result_btts_hit: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    # Best-EV outcome we'd have staked, the odds we got, and whether it won.
    best_ev_outcome: Mapped[str | None] = mapped_column(String(30), nullable=True)
    best_ev_odds: Mapped[Decimal | None] = mapped_column(Numeric(6, 3), nullable=True)
    best_ev_hit: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    # Profit / loss assuming a single-unit stake on the best-EV outcome.
    pnl_unit: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)

    settled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("prediction_id", name="uq_prediction_results_prediction"),
        Index("idx_results_match", "match_id"),
        Index("idx_results_settled", text("settled_at DESC")),
    )

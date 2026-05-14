"""arb_opportunities + user_arb_watchlist — M10 arbitrage scanner tables.

The arbitrage scanner finds risk-free betting opportunities across
bookmakers: when implied probabilities sum to less than 1.0, staking
proportionally on each outcome locks in a guaranteed profit.

Two tables:

* :class:`ArbOpportunity` — append-only book-of-record for every arb
  the scanner detects. Status starts as ``active``; transitions to
  ``expired`` (odds moved) or ``stale`` (kick-off passed).
* :class:`UserArbWatchlist` — per-user filter rules driving push
  notifications.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base

if TYPE_CHECKING:  # pragma: no cover
    pass


class ArbOpportunity(Base):
    __tablename__ = "arb_opportunities"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    match_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("matches.id", ondelete="CASCADE", name="fk_arb_opp_match"),
        nullable=False,
    )
    market_type: Mapped[str] = mapped_column(String(30), nullable=False)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    arb_total: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False)
    profit_margin: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False)
    # {outcome: {odds, bookmaker, captured_at}}
    best_odds: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    # {outcome: fraction_of_bankroll} — sums to 1.0
    stake_distribution: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'active'")
    )
    expired_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('active','expired','stale')",
            name="ck_arb_opportunities_status",
        ),
        CheckConstraint("arb_total > 0", name="ck_arb_opportunities_total"),
        CheckConstraint(
            "profit_margin >= 0", name="ck_arb_opportunities_margin"
        ),
        Index(
            "idx_arb_opp_match_market", "match_id", "market_type", "status"
        ),
        Index("idx_arb_opp_detected_at", "detected_at"),
    )


class UserArbWatchlist(Base):
    __tablename__ = "user_arb_watchlist"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE", name="fk_arb_watchlist_user"),
        nullable=False,
    )
    competition_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey(
            "competitions.id",
            ondelete="SET NULL",
            name="fk_arb_watchlist_competition",
        ),
        nullable=True,
    )
    # JSON array of market types the user watches. NULL = all markets.
    market_types: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    min_profit_margin: Mapped[Decimal] = mapped_column(
        Numeric(8, 6), nullable=False, server_default=text("0.01")
    )
    notify_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "min_profit_margin >= 0",
            name="ck_user_arb_watchlist_min_margin",
        ),
        Index(
            "idx_arb_watchlist_user_enabled", "user_id", "notify_enabled"
        ),
    )

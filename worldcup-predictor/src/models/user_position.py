"""user_positions — M9.5 live-hedging position tracker.

A row per external-platform bet the user has explicitly recorded. Distinct
from :class:`HedgeScenario` (a one-shot calculator snapshot) — a position
is a long-lived user record that the live-monitor worker watches for
hedge-window opportunities.

Status state machine::

    active ──► hedged    (user manually placed a hedge)
        │
        └───► settled    (settlement worker fills settlement_pnl)
        │
        └───► cancelled  (user-initiated soft delete)
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:  # pragma: no cover
    from .hedge_scenario import HedgeScenario
    from .push import PushNotification


class UserPosition(Base):
    __tablename__ = "user_positions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE", name="fk_user_positions_user"),
        nullable=False,
    )
    match_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("matches.id", ondelete="RESTRICT", name="fk_user_positions_match"),
        nullable=False,
    )
    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    market: Mapped[str] = mapped_column(String(30), nullable=False)
    outcome: Mapped[str] = mapped_column(String(30), nullable=False)
    stake: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    odds: Mapped[Decimal] = mapped_column(Numeric(8, 3), nullable=False)
    placed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'active'")
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    # Last time the live-monitor worker fired a hedge-window alert for this
    # position. Used to throttle alerts (no more than once per 30 minutes
    # per position) — guards against an oscillating odds market spamming
    # the user.
    last_alert_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Filled by `settle_positions_for_match` when the match is over. NULL
    # for any position still in active / hedged / cancelled state.
    settlement_pnl: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)

    # Relationships (back_populates wired in matching models below).
    triggered_scenarios: Mapped[list[HedgeScenario]] = relationship(
        back_populates="position",
        foreign_keys="HedgeScenario.position_id",
    )
    notifications: Mapped[list[PushNotification]] = relationship(
        back_populates="position",
        foreign_keys="PushNotification.position_id",
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('active','hedged','settled','cancelled')",
            name="ck_user_positions_status",
        ),
        CheckConstraint(
            "market IN ('1x2','over_under','asian_handicap','btts')",
            name="ck_user_positions_market",
        ),
        CheckConstraint("stake > 0", name="ck_user_positions_stake"),
        CheckConstraint("odds > 1.0", name="ck_user_positions_odds"),
        Index("idx_positions_user_status", "user_id", "status"),
        Index("idx_positions_match", "match_id"),
        # idx_positions_active_alert is a partial index created via raw SQL
        # in the migration (SQLAlchemy 2.0's Index() doesn't compose the
        # WHERE clause cleanly).
    )

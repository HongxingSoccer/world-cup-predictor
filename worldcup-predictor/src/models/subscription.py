"""subscriptions — per-user paid access windows.

A new row is appended every time a `payments.status` flips to 'paid' for a
basic / premium plan. The active subscription is the row where
``status='active' AND now() < expires_at``. `auto_renew=true` is reserved for
recurring plans (Phase 3.5 deliverable).

Tier convention:
    'basic'    — covers the bulk of paid features (1x2 + odds + stats).
    'premium'  — adds xG / injury panel + confidence-filter dashboards.

Plan types:
    'monthly'        — 30-day rolling.
    'worldcup_pass'  — single-payment access through the World-Cup window.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class Subscription(Base, TimestampMixin):
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    # 'basic' | 'premium'
    tier: Mapped[str] = mapped_column(String(20), nullable=False)
    # 'monthly' | 'worldcup_pass'
    plan_type: Mapped[str] = mapped_column(String(20), nullable=False)

    # 'active' | 'expired' | 'cancelled' | 'refunded'
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active", server_default="active"
    )
    price_cny: Mapped[int] = mapped_column(Integer, nullable=False)

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    auto_renew: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )

    payment_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("payments.id", ondelete="SET NULL"), nullable=True
    )

    __table_args__ = (
        Index("idx_subscriptions_user", "user_id", "status"),
        Index("idx_subscriptions_expires", "expires_at"),
    )

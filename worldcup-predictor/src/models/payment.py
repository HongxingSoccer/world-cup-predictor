"""payments — single source of truth for every paid transaction.

We deliberately split payments and subscriptions into two tables:
    - `payments` is event-driven (one row per Alipay / WeChat callback).
    - `subscriptions` is state-driven (one row per active access window).

A subscription is created (or extended) only AFTER its corresponding payment
moves to `status='paid'` via the channel callback handler. The callback
payload is stored verbatim in `callback_raw` for forensics / chargeback
disputes; `meta` carries application-level metadata (user agent, etc.).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class Payment(Base, TimestampMixin):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )

    # Internal order number — opaque to the user, sortable by ts prefix.
    order_no: Mapped[str] = mapped_column(String(64), nullable=False)
    # 'alipay' | 'wechat_pay'
    payment_channel: Mapped[str] = mapped_column(String(20), nullable=False)
    # Whole RMB cents.
    amount_cny: Mapped[int] = mapped_column(Integer, nullable=False)

    # 'pending' | 'paid' | 'failed' | 'refunded'
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", server_default="pending"
    )
    channel_trade_no: Mapped[str | None] = mapped_column(String(100), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    refunded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    callback_raw: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    meta: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        UniqueConstraint("order_no", name="uq_payments_order_no"),
        Index("idx_payments_user", "user_id"),
        Index("idx_payments_status", "status"),
    )

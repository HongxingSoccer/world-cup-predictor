"""share_links — short-link tracker for social sharing + referral attribution.

A logged-in user (or anonymous) creates a share link via
``POST /api/v1/share/create``; the service base62-encodes the row id into
`short_code` and exposes the link as ``https://wcp.app/s/{short_code}``.

The redirect handler increments `click_count`, the auth flow bumps
`register_count` when the share-link cookie is present at sign-up, and the
payment handler bumps `subscribe_count` on first paid order.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class ShareLink(Base):
    __tablename__ = "share_links"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    short_code: Mapped[str] = mapped_column(String(10), nullable=False)

    user_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    # 'prediction' | 'match' | 'track_record'
    target_type: Mapped[str] = mapped_column(String(20), nullable=False)
    target_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    target_url: Mapped[str] = mapped_column(Text, nullable=False)

    # Standard UTM fields piped through to analytics.
    utm_source: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    utm_medium: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    utm_campaign: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    click_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    register_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    subscribe_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("short_code", name="uq_share_links_short_code"),
        Index("idx_share_user", "user_id"),
        Index("idx_share_target", "target_type", "target_id"),
    )

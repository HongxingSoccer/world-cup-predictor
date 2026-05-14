"""push_notifications + user_push_settings — Phase 4 push subsystem.

Schemas follow ``docs/design/06_Phase4_ModelEvolution.md §5.3``.

* ``PushNotification`` — one row per *delivery attempt* (status moves
  ``pending → sent / failed → clicked``). The ``meta`` JSONB column stores
  the upstream provider response (WeChat msgid, Web Push 4xx body, …).
* ``UserPushSettings`` — one row per user with channel-specific recipients
  (wechat openid, Web Push subscription) and per-kind enable flags +
  optional quiet-hours window.
"""
from __future__ import annotations

from datetime import datetime, time
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    Time,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if False:  # TYPE_CHECKING-style guard (we need a literal-false symbol for SA forward refs)
    from .match import Match  # noqa: F401
    from .user_position import UserPosition


class PushNotification(Base):
    __tablename__ = "push_notifications"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    notification_type: Mapped[str] = mapped_column(String(30), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    target_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="pending")
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    clicked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    meta: Mapped[Any | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # M9.5 additions ----------------------------------------------------
    # When the notification was triggered by a user-tracked position
    # (hedge_window kind) or by a settled position (position_settled).
    position_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey(
            "user_positions.id",
            ondelete="CASCADE",
            name="fk_push_notifications_position",
        ),
        nullable=True,
    )
    # Match the notification refers to (deep-linkable from the
    # notification centre). Independent from position_id so a free
    # "match starting" alert can carry just match_id.
    match_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey(
            "matches.id",
            ondelete="SET NULL",
            name="fk_push_notifications_match",
        ),
        nullable=True,
    )
    # NULL = unread. Set by the notification-centre "mark read" endpoints.
    read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationship back to the position for the notification-detail panel.
    position: Mapped[UserPosition | None] = relationship(
        back_populates="notifications",
        foreign_keys=[position_id],
    )

    __table_args__ = (
        Index("idx_push_user", "user_id", "created_at"),
        Index("idx_push_status", "status"),
    )


class UserPushSettings(Base):
    __tablename__ = "user_push_settings"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    wechat_openid: Mapped[str | None] = mapped_column(String(100), nullable=True)
    web_push_subscription: Mapped[Any | None] = mapped_column(JSONB, nullable=True)
    enable_high_ev: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    enable_reports: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    enable_match_start: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    enable_red_hit: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    quiet_hours_start: Mapped[time | None] = mapped_column(Time, nullable=True)
    quiet_hours_end: Mapped[time | None] = mapped_column(Time, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (UniqueConstraint("user_id", name="uq_user_push_settings_user"),)

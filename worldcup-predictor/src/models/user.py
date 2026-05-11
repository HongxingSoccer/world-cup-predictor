"""users — primary identity table for the consumer-facing app.

`uuid` is the public-facing identifier carried in JWTs and exposed via the API
(e.g. /api/v1/users/me); `id` stays internal to the database. `password_hash`
is BCrypt and may be NULL for OAuth-only accounts. `phone` and `email` are
both individually nullable but at least one must be present at app-level
(enforced in `AuthService`, not in the schema, to allow phone-OTP-only and
email-OTP-only flows).
"""
from __future__ import annotations

import uuid as uuid_pkg
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Index,
    String,
    Text,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    uuid: Mapped[uuid_pkg.UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
        server_default=text("gen_random_uuid()"),
    )

    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # BCrypt hash (cost 12+ per coding standards). NULL for OAuth-only users.
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)

    nickname: Mapped[str | None] = mapped_column(String(50), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 'free' | 'basic' | 'premium'
    subscription_tier: Mapped[str] = mapped_column(
        String(20), nullable=False, default="free", server_default="free"
    )
    subscription_expires: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    locale: Mapped[str] = mapped_column(
        String(10), nullable=False, default="zh-CN", server_default="zh-CN"
    )
    timezone: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="Asia/Shanghai",
        server_default="Asia/Shanghai",
    )

    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    # 'user' | 'admin'
    role: Mapped[str] = mapped_column(
        String(20), nullable=False, default="user", server_default="user"
    )

    __table_args__ = (
        Index("uq_users_uuid", "uuid", unique=True),
        Index(
            "uq_users_phone",
            "phone",
            unique=True,
            postgresql_where=text("phone IS NOT NULL"),
        ),
        Index(
            "uq_users_email",
            "email",
            unique=True,
            postgresql_where=text("email IS NOT NULL"),
        ),
        Index("idx_users_subscription", "subscription_tier"),
    )

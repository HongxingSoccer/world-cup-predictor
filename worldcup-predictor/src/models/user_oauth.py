"""user_oauth — third-party identity bindings (WeChat / Weibo / Google / Apple).

A single `User` may have multiple OAuth bindings (one per provider). The
`(provider, provider_user_id)` pair uniquely identifies a remote account, so
duplicate sign-ins from the same provider link to the existing local user.

Tokens are stored at-rest encrypted at the application layer (the ORM stores
the ciphertext as TEXT). Decryption happens in `AuthService` only when
needed for refresh-token exchange.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class UserOAuth(Base):
    __tablename__ = "user_oauth"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # 'wechat' | 'weibo' | 'google' | 'apple'
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    provider_user_id: Mapped[str] = mapped_column(String(200), nullable=False)

    # Encrypted at the application layer (Phase 3.5: integrate KMS).
    access_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint(
            "provider", "provider_user_id", name="uq_user_oauth_provider_remote"
        ),
        Index("idx_oauth_user", "user_id"),
    )

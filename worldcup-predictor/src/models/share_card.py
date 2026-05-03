"""share_cards — pre-rendered social-share images.

We render a card image once and cache it in object storage (S3 / MinIO),
keying by ``(card_type, target_id, platform)`` so platform-specific aspect
ratios live as separate rows. Image URL is the fully-qualified CDN URL —
clients embed it in WeChat sharing payloads or Open-Graph tags.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    Index,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class ShareCard(Base):
    __tablename__ = "share_cards"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # 'prediction' | 'red_hit' | 'track_record'
    card_type: Mapped[str] = mapped_column(String(20), nullable=False)
    target_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    # 'wechat' | 'weibo' | 'douyin' | 'x' | 'generic'
    platform: Mapped[str] = mapped_column(String(20), nullable=False)

    image_url: Mapped[str] = mapped_column(Text, nullable=False)
    width: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    height: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("idx_cards_target", "card_type", "target_id"),
        Index("idx_cards_platform", "platform"),
    )

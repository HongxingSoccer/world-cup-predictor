"""match_features — versioned feature store for ML training and inference.

Features are stored as JSONB rather than as one column per signal so that
feature-set evolution (adding/removing/renaming columns) doesn't require a
DDL migration. `feature_version` lets multiple feature schemas coexist while
A/B-testing model versions.

Labels (`label_*`) are nullable: rows for upcoming matches are written without
labels and back-filled once the match finishes.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, SmallInteger, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class MatchFeature(Base):
    __tablename__ = "match_features"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    match_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("matches.id", ondelete="CASCADE"), nullable=False
    )
    feature_version: Mapped[str] = mapped_column(String(10), nullable=False)
    features: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    label_home_score: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)
    label_away_score: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)
    # 'H' (home win) | 'D' (draw) | 'A' (away win)
    label_result: Mapped[Optional[str]] = mapped_column(String(5), nullable=True)

    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint(
            "match_id", "feature_version", name="uq_match_features_match_version"
        ),
    )

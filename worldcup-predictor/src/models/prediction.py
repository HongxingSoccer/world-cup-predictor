"""predictions — append-only model output.

The table is the book of record for every published prediction. A PostgreSQL
trigger (created in the Phase-2 migration) rejects any UPDATE or DELETE so
the audit trail and SHA-256 `content_hash` stay tamper-evident: once a
prediction has been broadcast to users, it cannot be quietly rewritten.

Identifier convention:
    `model_version` is human-readable (e.g. ``"poisson_v1"``); `feature_version`
    is bumped independently when only the feature set changes.

JSONB columns:
    - `score_matrix`     — 10x10 list-of-lists of floats (P[home_goals][away_goals]).
    - `top_scores`       — list of `{ "score": "2-1", "prob": 0.084 }` sorted desc.
    - `over_under_probs` — `{ "2.5": { "over": 0.55, "under": 0.45 }, "3.5": ... }`.
    - `features_snapshot`— exact feature vector consumed at inference time.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    SmallInteger,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Prediction(Base):
    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    match_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("matches.id", ondelete="RESTRICT"), nullable=False
    )
    model_version: Mapped[str] = mapped_column(String(30), nullable=False)
    feature_version: Mapped[str] = mapped_column(String(10), nullable=False)

    prob_home_win: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    prob_draw: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    prob_away_win: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)

    lambda_home: Mapped[Decimal] = mapped_column(Numeric(5, 3), nullable=False)
    lambda_away: Mapped[Decimal] = mapped_column(Numeric(5, 3), nullable=False)

    score_matrix: Mapped[list[list[float]]] = mapped_column(JSONB, nullable=False)
    top_scores: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    over_under_probs: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    btts_prob: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)

    confidence_score: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    # 'low' | 'medium' | 'high'
    confidence_level: Mapped[str] = mapped_column(String(10), nullable=False)

    features_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    # SHA-256 hex digest of the canonicalized prediction body. Used by the
    # immutability check elsewhere in the platform.
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint(
            "match_id", "model_version", name="uq_predictions_match_model"
        ),
        Index("idx_predictions_published", text("published_at DESC")),
        Index("idx_predictions_confidence", text("confidence_score DESC")),
    )

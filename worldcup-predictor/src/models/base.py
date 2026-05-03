"""SQLAlchemy declarative base and shared mixins.

All ORM models in this package inherit from `Base`. Tables that need
audit timestamps (created_at / updated_at) additionally inherit from
`TimestampMixin`, which renders them as TIMESTAMPTZ columns backed by
PostgreSQL `NOW()` defaults and on-update triggers.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Project-wide declarative base."""


class TimestampMixin:
    """Adds created_at / updated_at TIMESTAMPTZ columns with server-side defaults."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

"""Database engine and session factory.

Single source of truth for the SQLAlchemy `Engine` and the `sessionmaker`
configured against `settings.DATABASE_URL`. Application code should depend on
`SessionLocal` (or `session_scope()`) rather than constructing its own engine.
"""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from src.config.settings import settings

# `pool_pre_ping` reconnects on stale connections (cloud DB drops idle conns).
# `future=True` enables 2.0-style usage even on older SQLAlchemy installs.
engine: Engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    future=True,
)

SessionLocal: sessionmaker[Session] = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
    future=True,
)


@contextmanager
def session_scope() -> Iterator[Session]:
    """Yield a session and commit/rollback automatically.

    Yields:
        An open `Session` bound to the project engine.

    Example:
        >>> with session_scope() as db:
        ...     db.add(some_model)
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

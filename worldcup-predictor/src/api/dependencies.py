"""FastAPI dependency providers.

Each provider is request-scoped and resolved via `Depends(...)` in the route
handlers. Keeping them in one file lets us swap any of them out at test time
with `app.dependency_overrides[...]` without touching the routes themselves.
"""
from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import structlog
from fastapi import Depends, Request
from sqlalchemy.orm import Session

from src.config.settings import settings
from src.ml.features.pipeline import FeaturePipeline
from src.ml.models.confidence import ConfidenceCalculator
from src.ml.models.poisson import PoissonBaselineModel
from src.ml.odds.analyzer import OddsAnalyzer
from src.ml.prediction_service import PredictionService
from src.services.feature_flags import (
    DEFAULT_FLAGS,
    FeatureFlagsService,
    InMemoryFlagBackend,
)
from src.utils.db import SessionLocal

logger = structlog.get_logger(__name__)


def get_db_session() -> Iterator[Session]:
    """Per-request SQLAlchemy session, committed/rolled back by the framework."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_model(request: Request) -> PoissonBaselineModel:
    """Return the model loaded into `app.state.model` at startup."""
    model: PoissonBaselineModel | None = getattr(request.app.state, "model", None)
    if model is None:
        # Local fallback so tests + dev environments don't have to wire MLflow.
        # Production startup overwrites app.state.model with a real artifact.
        logger.warning("model_not_loaded_using_untrained_default")
        model = PoissonBaselineModel()
    return model


def get_redis(request: Request) -> Any | None:
    """Return the redis client from app.state, or None if Redis is disabled."""
    return getattr(request.app.state, "redis", None)


def get_prediction_service(
    db_session: Session = Depends(get_db_session),
    model: PoissonBaselineModel = Depends(get_model),
) -> PredictionService:
    """Wire up the four collaborators into a request-scoped PredictionService."""
    return PredictionService(
        db_session=db_session,
        model=model,
        feature_pipeline=FeaturePipeline(db_session),
        odds_analyzer=OddsAnalyzer(db_session),
        confidence_calculator=ConfidenceCalculator(),
    )


def predictions_today_cache_ttl() -> int:
    return settings.PREDICTIONS_TODAY_CACHE_TTL


# --- Phase 5 ----------------------------------------------------------------


def get_feature_flags(request: Request) -> FeatureFlagsService:
    """Singleton FeatureFlagsService stored on app.state.

    Tests override this via ``app.dependency_overrides`` with their own
    pre-populated service.
    """
    svc: FeatureFlagsService | None = getattr(request.app.state, "feature_flags", None)
    if svc is None:
        # Lazily build a no-Redis fallback so dev/test environments work
        # without configuring Redis. Production startup MUST install a
        # real (Redis-backed) service onto app.state.feature_flags.
        svc = FeatureFlagsService(
            InMemoryFlagBackend(),
            defaults=DEFAULT_FLAGS,
            refresh_seconds=settings.FEATURE_FLAGS_REFRESH_SECONDS,
        )
        request.app.state.feature_flags = svc
    return svc


def require_admin(request: Request) -> None:
    """Reject the request unless ``X-Admin-Token`` matches the configured token.

    Returns ``None`` so route handlers can use it as a side-effect dependency:
    ``Depends(require_admin)``.
    """
    from fastapi import HTTPException, status  # local import keeps deps light

    expected = settings.ADMIN_API_TOKEN
    if not expected:
        # Admin API is only enabled when the operator sets ADMIN_API_TOKEN.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="admin api disabled"
        )
    received = request.headers.get("x-admin-token") or request.headers.get(
        "X-Admin-Token"
    )
    if received != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid admin token"
        )

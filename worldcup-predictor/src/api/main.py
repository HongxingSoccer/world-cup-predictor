"""FastAPI application entrypoint.

Boots the inference service: configures structured logging, mounts middlewares
(API key → rate limit → access log → CORS), wires the four routers, and tries
to load the production model from MLflow at startup. When MLflow isn't
reachable (local dev without `mlflow-server` running) the service falls back
to an untrained `PoissonBaselineModel` so endpoints still serve, with the
`/model/health` route surfacing the degraded state.

Run locally:

    uvicorn src.api:app --reload --port 8000
"""
from __future__ import annotations

import contextlib
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.api.middleware import (
    AccessLogMiddleware,
    APIKeyMiddleware,
    RateLimitMiddleware,
)
from src.api.routes import (
    admin,
    client_errors,
    fx,
    health,
    hedge,
    markets,
    matches,
    notifications,
    odds,
    positions,
    predict,
    predictions,
    push_settings,
    reports,
    track_record,
    worldcup,
)
from src.config.settings import settings
from src.ml.models.poisson import PoissonBaselineModel
from src.utils.logging import configure_logging

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown hook."""
    configure_logging(json_logs=True)
    app.state.model = _load_production_model()
    app.state.redis = _maybe_redis()
    logger.info(
        "api_started",
        model=app.state.model.get_model_version(),
        trained=bool(app.state.model.params),
        redis=bool(app.state.redis),
    )
    try:
        yield
    finally:
        if app.state.redis is not None:
            # Best-effort shutdown — Redis may already be gone in CI / tests.
            with contextlib.suppress(Exception):  # pragma: no cover
                app.state.redis.close()


def _create_app() -> FastAPI:
    app = FastAPI(
        title="World Cup 2026 Predictor — Inference API",
        version="0.2.0",
        description="ML inference + odds analysis (Phase 2).",
        lifespan=lifespan,
    )

    # Middleware order matters: outermost wraps innermost. We want CORS first
    # (handles preflights), then access-log (so 401/429 are still logged),
    # then rate limit, then API-key auth.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.API_CORS_ORIGINS),
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(AccessLogMiddleware)
    app.add_middleware(
        RateLimitMiddleware,
        requests_per_minute=settings.API_RATE_LIMIT_PER_MIN,
    )
    app.add_middleware(APIKeyMiddleware)

    # Global exception handlers — keep response shape consistent.
    @app.exception_handler(RequestValidationError)
    async def _on_validation_error(_: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"code": 40000, "error": "VALIDATION_ERROR", "details": exc.errors()},
        )

    @app.exception_handler(ValueError)
    async def _on_value_error(_: Request, exc: ValueError):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"code": 40001, "error": "BAD_REQUEST", "message": str(exc)},
        )

    @app.exception_handler(Exception)
    async def _on_unexpected(_: Request, exc: Exception):
        logger.exception("api_unexpected_error", error=str(exc))
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"code": 50000, "error": "INTERNAL_ERROR", "message": "internal server error"},
        )

    # Routers
    app.include_router(health.router)
    app.include_router(predict.router)
    app.include_router(odds.router)
    app.include_router(predictions.router)
    app.include_router(matches.router)
    app.include_router(track_record.router)
    app.include_router(reports.router)
    app.include_router(client_errors.router)
    app.include_router(fx.router)
    app.include_router(markets.router)
    app.include_router(worldcup.router)
    app.include_router(worldcup.competitions_router)
    app.include_router(push_settings.router)
    app.include_router(admin.router)
    app.include_router(hedge.router)
    app.include_router(positions.router)
    app.include_router(notifications.router)

    @app.get("/", include_in_schema=False)
    def _root() -> dict[str, str]:
        return {"service": "wcp-ml-api", "docs": "/docs"}

    return app


def _load_production_model():  # type: ignore[no-untyped-def]
    """Try MLflow → untrained fallback. Subclass is dispatched by name."""
    try:
        from src.ml.training.mlflow_utils import load_production_model

        loaded = load_production_model(settings.ACTIVE_MODEL_NAME)
        if loaded is not None:
            return loaded
    except Exception as exc:  # mlflow unreachable, missing model, etc.
        logger.warning("mlflow_load_failed", error=str(exc))
    logger.warning(
        "model_falling_back_to_untrained_default",
        active_model=settings.ACTIVE_MODEL_NAME,
    )
    return PoissonBaselineModel()


def _maybe_redis():  # type: ignore[no-untyped-def]
    """Return a redis client, or None if redis is unreachable."""
    try:
        import redis

        client = redis.Redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=2.0,
            socket_timeout=5.0,
        )
        client.ping()
        return client
    except Exception as exc:
        logger.warning("redis_unavailable", error=str(exc))
        return None


app = _create_app()

"""GET /health (cheap liveness) + GET /api/v1/model/health (model state)."""
from __future__ import annotations

import time
from datetime import UTC, datetime

from fastapi import APIRouter, Depends

from src.api.dependencies import get_model
from src.ml.models.poisson import PoissonBaselineModel

router = APIRouter(tags=["health"])


@router.get("/health")
def liveness() -> dict[str, str]:
    """Cheap liveness probe used by Dockerfile HEALTHCHECK and K8s livenessProbe.

    Deliberately does NOT touch the DB / Redis / model state — anything
    that talks to a dependency belongs in /readyz (TODO) so a transient
    upstream blip can't trigger pod restarts.
    """
    return {"status": "ok", "service": "wcp-ml-api"}


@router.get("/api/v1/model/health")
def model_health(model: PoissonBaselineModel = Depends(get_model)) -> dict[str, object]:
    """Return basic service info: model version, training status, uptime."""
    started_at = getattr(router, "_started_at", time.monotonic())
    if not hasattr(router, "_started_at"):
        router._started_at = started_at  # type: ignore[attr-defined]

    is_trained = bool(model.params)
    return {
        "model_version": model.get_model_version(),
        "trained": is_trained,
        "trained_on_n_matches": model.params.get("trained_on_n_matches"),
        "status": "ok" if is_trained else "untrained",
        "uptime_seconds": round(time.monotonic() - started_at, 2),
        "checked_at": datetime.now(UTC).isoformat(),
    }

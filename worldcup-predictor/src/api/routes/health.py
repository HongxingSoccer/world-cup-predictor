"""GET /api/v1/model/health — model + service liveness check."""
from __future__ import annotations

import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from src.api.dependencies import get_model
from src.ml.models.poisson import PoissonBaselineModel

router = APIRouter(prefix="/api/v1", tags=["health"])


@router.get("/model/health")
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
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }

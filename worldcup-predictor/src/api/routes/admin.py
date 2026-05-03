"""Operations admin API (Phase 5, design §4.4).

This router exposes lightweight read/aggregate endpoints + a feature-flag
editor that the frontend ``/admin/*`` pages consume. Every route is guarded
by :func:`src.api.dependencies.require_admin`, which expects an
``X-Admin-Token`` header matching ``settings.ADMIN_API_TOKEN``.

The aggregations are intentionally simple (single-table count queries) —
heavy business analytics live in the data warehouse / Grafana dashboards
defined in §4.3.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.api.dependencies import (
    get_db_session,
    get_feature_flags,
    require_admin,
)
from src.models.analysis_report import AnalysisReport
from src.models.prediction import Prediction
from src.models.push import PushNotification
from src.models.user import User
from src.services.feature_flags import FeatureFlagsService

router = APIRouter(
    prefix="/api/v1/admin",
    tags=["admin"],
    dependencies=[Depends(require_admin)],
)


# --- Schemas ---------------------------------------------------------------


class OverviewCard(BaseModel):
    label: str
    value: int
    delta_24h: Optional[int] = None


class OverviewResponse(BaseModel):
    cards: list[OverviewCard]
    generated_at: datetime


class PaginatedUsers(BaseModel):
    total: int
    items: list[dict[str, Any]]


class FlagsResponse(BaseModel):
    flags: dict[str, bool]


class FlagUpdateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    value: bool


# --- Routes ----------------------------------------------------------------


@router.get("", response_model=OverviewResponse)
def admin_overview(
    db: Session = Depends(get_db_session),
) -> OverviewResponse:
    """Top-level KPI cards for the admin dashboard (§4.4.1 row 1)."""
    now = datetime.now(timezone.utc)
    yesterday = now - timedelta(hours=24)

    user_count = int(db.execute(select(func.count(User.id))).scalar_one())
    user_count_24h = int(
        db.execute(
            select(func.count(User.id)).where(User.created_at >= yesterday)
        ).scalar_one()
    )
    pred_count = int(db.execute(select(func.count(Prediction.id))).scalar_one())
    report_count = int(
        db.execute(select(func.count(AnalysisReport.id))).scalar_one()
    )
    push_24h = int(
        db.execute(
            select(func.count(PushNotification.id)).where(
                PushNotification.created_at >= yesterday
            )
        ).scalar_one()
    )

    return OverviewResponse(
        generated_at=now,
        cards=[
            OverviewCard(label="users_total", value=user_count, delta_24h=user_count_24h),
            OverviewCard(label="predictions_total", value=pred_count),
            OverviewCard(label="reports_total", value=report_count),
            OverviewCard(label="push_24h", value=push_24h),
        ],
    )


@router.get("/users", response_model=PaginatedUsers)
def admin_list_users(
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db_session),
) -> PaginatedUsers:
    """Paginated user listing for the /admin/users page."""
    limit = max(1, min(limit, 200))
    offset = max(0, offset)
    total = int(db.execute(select(func.count(User.id))).scalar_one())
    rows = db.execute(
        select(User).order_by(User.created_at.desc()).limit(limit).offset(offset)
    ).scalars().all()
    items = [
        {
            "id": u.id,
            "uuid": str(u.uuid),
            "email": u.email,
            "subscription_tier": getattr(u, "subscription_tier", "free"),
            "created_at": u.created_at,
        }
        for u in rows
    ]
    return PaginatedUsers(total=total, items=items)


@router.get("/system/flags", response_model=FlagsResponse)
def admin_get_flags(
    flags: FeatureFlagsService = Depends(get_feature_flags),
) -> FlagsResponse:
    return FlagsResponse(flags=flags.all_flags())


@router.put("/system/flags", response_model=FlagsResponse)
def admin_update_flag(
    payload: FlagUpdateRequest,
    flags: FeatureFlagsService = Depends(get_feature_flags),
) -> FlagsResponse:
    try:
        flags.set_flag(payload.name, payload.value)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"unknown flag: {payload.name}",
        )
    return FlagsResponse(flags=flags.all_flags())

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
from src.models.data_source_log import DataSourceLog
from src.models.payment import Payment
from src.models.prediction import Prediction
from src.models.push import PushNotification
from src.models.subscription import Subscription
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


# --- Phase 5 admin pages -------------------------------------------------


class PaginatedItems(BaseModel):
    total: int
    items: list[dict[str, Any]]


def _clamp(limit: int, offset: int) -> tuple[int, int]:
    return max(1, min(limit, 200)), max(0, offset)


@router.get("/subscriptions", response_model=PaginatedItems)
def admin_list_subscriptions(
    limit: int = 50,
    offset: int = 0,
    status: Optional[str] = None,
    db: Session = Depends(get_db_session),
) -> PaginatedItems:
    limit, offset = _clamp(limit, offset)
    count_q = select(func.count(Subscription.id))
    rows_q = (
        select(Subscription, User.email)
        .join(User, User.id == Subscription.user_id, isouter=True)
        .order_by(Subscription.created_at.desc())
    )
    if status:
        count_q = count_q.where(Subscription.status == status)
        rows_q = rows_q.where(Subscription.status == status)
    total = int(db.execute(count_q).scalar_one())
    rows = db.execute(rows_q.limit(limit).offset(offset)).all()
    items = [
        {
            "id": s.id,
            "user_id": s.user_id,
            "user_email": email,
            "tier": s.tier,
            "plan_type": s.plan_type,
            "status": s.status,
            "price_cny": s.price_cny,
            "started_at": s.started_at,
            "expires_at": s.expires_at,
        }
        for (s, email) in rows
    ]
    return PaginatedItems(total=total, items=items)


@router.get("/payments", response_model=PaginatedItems)
def admin_list_payments(
    limit: int = 50,
    offset: int = 0,
    status: Optional[str] = None,
    db: Session = Depends(get_db_session),
) -> PaginatedItems:
    limit, offset = _clamp(limit, offset)
    count_q = select(func.count(Payment.id))
    rows_q = select(Payment).order_by(Payment.created_at.desc())
    if status:
        count_q = count_q.where(Payment.status == status)
        rows_q = rows_q.where(Payment.status == status)
    total = int(db.execute(count_q).scalar_one())
    rows = db.execute(rows_q.limit(limit).offset(offset)).scalars().all()
    items = [
        {
            "id": p.id,
            "user_id": p.user_id,
            "order_no": p.order_no,
            "payment_channel": p.payment_channel,
            "amount_cny": p.amount_cny,
            "status": p.status,
            "paid_at": p.paid_at,
        }
        for p in rows
    ]
    return PaginatedItems(total=total, items=items)


@router.get("/predictions", response_model=PaginatedItems)
def admin_list_predictions(
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db_session),
) -> PaginatedItems:
    limit, offset = _clamp(limit, offset)
    total = int(db.execute(select(func.count(Prediction.id))).scalar_one())
    rows = db.execute(
        select(Prediction)
        .order_by(Prediction.published_at.desc())
        .limit(limit)
        .offset(offset)
    ).scalars().all()
    items = [
        {
            "id": p.id,
            "match_id": p.match_id,
            "model_version": p.model_version,
            "confidence_score": p.confidence_score,
            "confidence_level": p.confidence_level,
            "published_at": p.published_at,
        }
        for p in rows
    ]
    return PaginatedItems(total=total, items=items)


def _report_dict(r: AnalysisReport) -> dict[str, Any]:
    return {
        "id": r.id,
        "match_id": r.match_id,
        "title": r.title,
        "summary": r.summary,
        "model_used": r.model_used,
        "status": r.status,
        "generated_at": r.generated_at,
        "published_at": r.published_at,
    }


def _list_reports(
    db: Session, limit: int, offset: int, status_filter: Optional[str]
) -> PaginatedItems:
    limit, offset = _clamp(limit, offset)
    count_q = select(func.count(AnalysisReport.id))
    rows_q = select(AnalysisReport).order_by(AnalysisReport.generated_at.desc())
    if status_filter:
        count_q = count_q.where(AnalysisReport.status == status_filter)
        rows_q = rows_q.where(AnalysisReport.status == status_filter)
    total = int(db.execute(count_q).scalar_one())
    rows = db.execute(rows_q.limit(limit).offset(offset)).scalars().all()
    return PaginatedItems(total=total, items=[_report_dict(r) for r in rows])


@router.get("/reports", response_model=PaginatedItems)
def admin_list_reports(
    limit: int = 50,
    offset: int = 0,
    status: Optional[str] = None,
    db: Session = Depends(get_db_session),
) -> PaginatedItems:
    return _list_reports(db, limit, offset, status)


@router.post("/reports/{report_id}/publish")
def admin_publish_report(
    report_id: int,
    db: Session = Depends(get_db_session),
) -> dict[str, Any]:
    row = db.get(AnalysisReport, report_id)
    if row is None:
        raise HTTPException(status_code=404, detail="report not found")
    row.status = "published"
    row.published_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)
    return _report_dict(row)


@router.post("/reports/{report_id}/reject")
def admin_reject_report(
    report_id: int,
    db: Session = Depends(get_db_session),
) -> dict[str, Any]:
    row = db.get(AnalysisReport, report_id)
    if row is None:
        raise HTTPException(status_code=404, detail="report not found")
    row.status = "rejected"
    db.commit()
    db.refresh(row)
    return _report_dict(row)


@router.get("/data-sources", response_model=PaginatedItems)
def admin_list_data_sources(
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db_session),
) -> PaginatedItems:
    limit, offset = _clamp(limit, offset)
    total = int(db.execute(select(func.count(DataSourceLog.id))).scalar_one())
    rows = db.execute(
        select(DataSourceLog)
        .order_by(DataSourceLog.started_at.desc())
        .limit(limit)
        .offset(offset)
    ).scalars().all()
    items = [
        {
            "id": d.id,
            "source_name": d.source_name,
            "task_type": d.task_type,
            "status": d.status,
            "records_fetched": d.records_fetched,
            "records_inserted": d.records_inserted,
            "started_at": d.started_at,
            "finished_at": d.finished_at,
            "error_message": d.error_message,
        }
        for d in rows
    ]
    return PaginatedItems(total=total, items=items)


@router.get("/data-sources/summary")
def admin_data_sources_summary(
    db: Session = Depends(get_db_session),
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    yesterday = now - timedelta(hours=24)
    sources = [
        s for (s,) in db.execute(
            select(DataSourceLog.source_name).distinct()
        ).all()
    ]
    out: list[dict[str, Any]] = []
    for name in sources:
        last = db.execute(
            select(DataSourceLog)
            .where(DataSourceLog.source_name == name)
            .order_by(DataSourceLog.started_at.desc())
            .limit(1)
        ).scalar_one_or_none()
        success_24h = int(
            db.execute(
                select(func.count(DataSourceLog.id)).where(
                    DataSourceLog.source_name == name,
                    DataSourceLog.status == "success",
                    DataSourceLog.started_at >= yesterday,
                )
            ).scalar_one()
        )
        failed_24h = int(
            db.execute(
                select(func.count(DataSourceLog.id)).where(
                    DataSourceLog.source_name == name,
                    DataSourceLog.status == "failed",
                    DataSourceLog.started_at >= yesterday,
                )
            ).scalar_one()
        )
        out.append(
            {
                "source_name": name,
                "last_run_at": last.started_at if last else None,
                "last_status": last.status if last else None,
                "success_24h": success_24h,
                "failed_24h": failed_24h,
            }
        )
    return {"sources": out}


@router.get("/push", response_model=PaginatedItems)
def admin_list_push(
    limit: int = 50,
    offset: int = 0,
    status: Optional[str] = None,
    db: Session = Depends(get_db_session),
) -> PaginatedItems:
    limit, offset = _clamp(limit, offset)
    count_q = select(func.count(PushNotification.id))
    rows_q = select(PushNotification).order_by(PushNotification.created_at.desc())
    if status:
        count_q = count_q.where(PushNotification.status == status)
        rows_q = rows_q.where(PushNotification.status == status)
    total = int(db.execute(count_q).scalar_one())
    rows = db.execute(rows_q.limit(limit).offset(offset)).scalars().all()
    items = [
        {
            "id": n.id,
            "user_id": n.user_id,
            "channel": n.channel,
            "notification_type": n.notification_type,
            "title": n.title,
            "status": n.status,
            "sent_at": n.sent_at,
            "created_at": n.created_at,
        }
        for n in rows
    ]
    return PaginatedItems(total=total, items=items)


@router.get("/push/summary")
def admin_push_summary(
    db: Session = Depends(get_db_session),
) -> dict[str, int]:
    now = datetime.now(timezone.utc)
    yesterday = now - timedelta(hours=24)
    pending = int(
        db.execute(
            select(func.count(PushNotification.id)).where(
                PushNotification.status == "pending"
            )
        ).scalar_one()
    )
    sent_24h = int(
        db.execute(
            select(func.count(PushNotification.id)).where(
                PushNotification.status == "sent",
                PushNotification.created_at >= yesterday,
            )
        ).scalar_one()
    )
    failed_24h = int(
        db.execute(
            select(func.count(PushNotification.id)).where(
                PushNotification.status == "failed",
                PushNotification.created_at >= yesterday,
            )
        ).scalar_one()
    )
    click_through_24h = int(
        db.execute(
            select(func.count(PushNotification.id)).where(
                PushNotification.clicked_at.is_not(None),
                PushNotification.created_at >= yesterday,
            )
        ).scalar_one()
    )
    return {
        "pending": pending,
        "sent_24h": sent_24h,
        "failed_24h": failed_24h,
        "click_through_24h": click_through_24h,
    }


@router.get("/content/moderation", response_model=PaginatedItems)
def admin_content_moderation(
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db_session),
) -> PaginatedItems:
    return _list_reports(db, limit, offset, "draft")

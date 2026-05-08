"""Phase 4 push endpoints: GET/PUT /api/v1/push/settings, POST /api/v1/push/test.

* ``settings``  reads/upserts a single ``user_push_settings`` row keyed by
  ``user_id``. Pydantic models mirror the design-doc field set 1:1.
* ``test`` enqueues a synchronous test push for the authenticated user
  (admin-gated in production). Currently a stub that returns the payload it
  *would* dispatch — the full pipeline lives in
  :func:`src.tasks.phase4_tasks.fan_out_notification`.
"""
from __future__ import annotations

from datetime import time
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.api.dependencies import get_db_session
from src.models.push import UserPushSettings

router = APIRouter(prefix="/api/v1/push", tags=["push"])


class PushSettingsIn(BaseModel):
    user_id: int = Field(..., gt=0)
    wechat_openid: Optional[str] = Field(None, max_length=100)
    web_push_subscription: Optional[dict[str, Any]] = None
    enable_high_ev: bool = True
    enable_reports: bool = True
    enable_match_start: bool = True
    enable_red_hit: bool = True
    quiet_hours_start: Optional[time] = None
    quiet_hours_end: Optional[time] = None


class PushSettingsOut(PushSettingsIn):
    id: int


def _to_out(row: UserPushSettings) -> PushSettingsOut:
    return PushSettingsOut(
        id=row.id,
        user_id=row.user_id,
        wechat_openid=row.wechat_openid,
        web_push_subscription=row.web_push_subscription,
        enable_high_ev=row.enable_high_ev,
        enable_reports=row.enable_reports,
        enable_match_start=row.enable_match_start,
        enable_red_hit=row.enable_red_hit,
        quiet_hours_start=row.quiet_hours_start,
        quiet_hours_end=row.quiet_hours_end,
    )


@router.get("/settings", response_model=PushSettingsOut)
def get_settings(
    user_id: int, session: Session = Depends(get_db_session)
) -> PushSettingsOut:
    """Return the user's push prefs.

    First-time callers (no row yet) get the design-doc defaults — every
    channel enabled, no quiet hours — so the settings page renders a
    populated form on first visit instead of erroring out. ``id`` falls back
    to 0 in that case to signal "not yet persisted".
    """
    row = (
        session.query(UserPushSettings)
        .filter(UserPushSettings.user_id == user_id)
        .one_or_none()
    )
    if row is None:
        return PushSettingsOut(
            id=0,
            user_id=user_id,
            wechat_openid=None,
            web_push_subscription=None,
            enable_high_ev=True,
            enable_reports=True,
            enable_match_start=True,
            enable_red_hit=True,
            quiet_hours_start=None,
            quiet_hours_end=None,
        )
    return _to_out(row)


@router.put("/settings", response_model=PushSettingsOut)
def upsert_settings(
    payload: PushSettingsIn, session: Session = Depends(get_db_session)
) -> PushSettingsOut:
    row = (
        session.query(UserPushSettings)
        .filter(UserPushSettings.user_id == payload.user_id)
        .one_or_none()
    )
    if row is None:
        row = UserPushSettings(**payload.model_dump())
        session.add(row)
    else:
        for k, v in payload.model_dump().items():
            setattr(row, k, v)
    session.flush()
    return _to_out(row)


class PushTestIn(BaseModel):
    user_id: int = Field(..., gt=0)
    channel: str = Field(..., min_length=1, max_length=20)
    title: str = Field(..., min_length=1, max_length=200)
    body: str = Field(..., min_length=1, max_length=2000)


@router.post("/test")
def trigger_test_push(payload: PushTestIn) -> dict:
    """Dry-run a test push — returns the payload that would be delivered.

    The actual fan-out runs in :func:`fan_out_notification` (Celery). This
    endpoint exists so admins can validate per-user prefs without writing
    to the live ``push_notifications`` table.
    """
    return {
        "status": "queued",
        "preview": payload.model_dump(),
    }

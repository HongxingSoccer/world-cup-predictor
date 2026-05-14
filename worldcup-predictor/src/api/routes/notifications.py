"""Notification centre API (M9.5).

The bell-icon drawer on the frontend reads from here. Everything is
scoped to the calling user; java-api passes the authenticated user id
in the X-User-Id header.
"""
from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import desc, select, update
from sqlalchemy.orm import Session

from src.api.dependencies import get_db_session
from src.models.push import PushNotification

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


def _user_id_from_header(
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
) -> int:
    if x_user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-User-Id header required",
        )
    try:
        return int(x_user_id)
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-User-Id must be an integer",
        ) from exc


def _row_to_dict(n: PushNotification) -> dict:
    return {
        "id": n.id,
        "kind": n.notification_type,
        "title": n.title,
        "body": n.body,
        "position_id": n.position_id,
        "match_id": n.match_id,
        "target_url": n.target_url,
        "payload": n.meta or {},
        "created_at": n.created_at.isoformat() if n.created_at else None,
        "read_at": n.read_at.isoformat() if n.read_at else None,
    }


@router.get("/")
def list_notifications(
    limit: int = 50,
    session: Session = Depends(get_db_session),
    user_id: int = Depends(_user_id_from_header),
) -> dict:
    rows = (
        session.execute(
            select(PushNotification)
            .where(PushNotification.user_id == user_id)
            .order_by(desc(PushNotification.created_at))
            .limit(min(limit, 200))
        )
        .scalars()
        .all()
    )
    unread_count = session.execute(
        select(PushNotification)
        .where(
            PushNotification.user_id == user_id,
            PushNotification.read_at.is_(None),
        )
    ).scalars().all()
    return {
        "items": [_row_to_dict(n) for n in rows],
        "unread_count": len(unread_count),
    }


@router.get("/unread-count")
def unread_count(
    session: Session = Depends(get_db_session),
    user_id: int = Depends(_user_id_from_header),
) -> dict:
    rows = session.execute(
        select(PushNotification.id)
        .where(
            PushNotification.user_id == user_id,
            PushNotification.read_at.is_(None),
        )
    ).all()
    return {"unread_count": len(rows)}


@router.patch("/{notification_id}/read")
def mark_read(
    notification_id: int,
    session: Session = Depends(get_db_session),
    user_id: int = Depends(_user_id_from_header),
) -> dict:
    row = session.get(PushNotification, notification_id)
    if row is None or row.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"notification {notification_id} not found",
        )
    if row.read_at is None:
        row.read_at = datetime.now(UTC)
        session.commit()
    return _row_to_dict(row)


@router.post("/read-all")
def mark_all_read(
    session: Session = Depends(get_db_session),
    user_id: int = Depends(_user_id_from_header),
) -> dict:
    now = datetime.now(UTC)
    result = session.execute(
        update(PushNotification)
        .where(
            PushNotification.user_id == user_id,
            PushNotification.read_at.is_(None),
        )
        .values(read_at=now)
    )
    session.commit()
    return {"updated": result.rowcount or 0}


__all__ = ["router"]

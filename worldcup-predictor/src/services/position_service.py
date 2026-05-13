"""Position CRUD service.

Pure database operations against :class:`UserPosition`. Authorization
(user-scoped reads/writes) lives here, so every controller layer can stay
a thin pass-through.
"""
from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from src.api.schemas.positions import (
    CreatePositionRequest,
    PositionStatus,
)
from src.models.match import Match
from src.models.user_position import UserPosition

logger = logging.getLogger(__name__)


class PositionService:
    """Static-method service — state-free DB ops."""

    @staticmethod
    def create(
        session: Session, user_id: int, req: CreatePositionRequest
    ) -> UserPosition:
        """Insert a new position. Caller already validated the body."""
        # Quick sanity check that the match exists; lets us 404 here
        # rather than relying on FK error 500 surfacing.
        if session.get(Match, req.match_id) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"match {req.match_id} not found",
            )

        position = UserPosition(
            user_id=user_id,
            match_id=req.match_id,
            platform=req.platform,
            market=req.market,
            outcome=req.outcome,
            stake=req.stake,
            odds=req.odds,
            placed_at=req.placed_at,
            notes=req.notes,
        )
        session.add(position)
        session.flush()
        session.commit()
        return position

    @staticmethod
    def list_for_user(
        session: Session,
        user_id: int,
        position_status: PositionStatus | None = None,
        limit: int = 50,
    ) -> list[UserPosition]:
        stmt = (
            select(UserPosition)
            .where(UserPosition.user_id == user_id)
            .order_by(desc(UserPosition.created_at))
            .limit(limit)
        )
        if position_status is not None:
            stmt = stmt.where(UserPosition.status == position_status)
        return list(session.execute(stmt).scalars().all())

    @staticmethod
    def get_for_user(
        session: Session, user_id: int, position_id: int
    ) -> UserPosition:
        """Fetch a position. 403 if it's not the caller's, 404 if absent.

        We use 404 instead of 403 for the cross-user case to avoid leaking
        whether a given ID exists for some other user.
        """
        position = session.get(UserPosition, position_id)
        if position is None or position.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"position {position_id} not found",
            )
        return position

    @staticmethod
    def update_status(
        session: Session,
        user_id: int,
        position_id: int,
        new_status: PositionStatus,
    ) -> UserPosition:
        position = PositionService.get_for_user(session, user_id, position_id)
        position.status = new_status
        position.updated_at = datetime.utcnow()
        session.commit()
        return position

    @staticmethod
    def soft_delete(
        session: Session, user_id: int, position_id: int
    ) -> UserPosition:
        """Soft-delete = transition to 'cancelled'. Preserves audit trail."""
        return PositionService.update_status(
            session, user_id, position_id, "cancelled"
        )

    @staticmethod
    def mark_settled(
        session: Session,
        position_id: int,
        pnl: Decimal,
    ) -> UserPosition:
        """Internal helper for the settlement worker (no user scope)."""
        position = session.get(UserPosition, position_id)
        if position is None:
            raise ValueError(f"position {position_id} not found")
        position.status = "settled"
        position.settlement_pnl = pnl
        position.updated_at = datetime.utcnow()
        session.commit()
        return position

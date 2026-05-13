"""M9.5 positions API — user bet-tracker CRUD + on-demand opportunity check.

All endpoints sit behind the `APIKeyMiddleware` (the Java business API
forwards calls in with the internal X-API-Key). User identity is carried
via the ``X-User-Id`` header that java-api sets after JWT validation.

The 4 routes:

  POST   /api/v1/positions                          create
  GET    /api/v1/positions                          list (caller's)
  GET    /api/v1/positions/{id}                     detail + live hedge-window snapshot
  PATCH  /api/v1/positions/{id}/status              status transition
  DELETE /api/v1/positions/{id}                     soft-delete (status='cancelled')
  POST   /api/v1/positions/{id}/check-opportunity   run the detector now
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from src.api.dependencies import get_db_session, get_prediction_service
from src.api.schemas.positions import (
    CreatePositionRequest,
    HedgeOpportunitySummary,
    PositionResponse,
    PositionStatus,
    UpdateStatusRequest,
)
from src.ml.hedge.opportunity_detector import HedgeOpportunityDetector
from src.models.match import Match
from src.models.user_position import UserPosition
from src.services.position_service import PositionService

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/api/v1/positions", tags=["positions"])


def _user_id_from_header(
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
) -> int:
    """Resolve the caller's id. The Java business API attaches X-User-Id
    after JWT validation; direct ml-api callers (CLI, tests) can spoof it."""
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


def _match_summary(session: Session, match_id: int) -> dict[str, Any] | None:
    """Lightweight `{home, away, kickoff_time}` dict for the response."""
    match = session.get(Match, match_id)
    if match is None:
        return None
    return {
        "match_id": match.id,
        "home_team_id": match.home_team_id,
        "away_team_id": match.away_team_id,
        "kickoff_time": match.match_date.isoformat() if match.match_date else None,
        "status": match.status,
    }


def _to_response(
    session: Session,
    position: UserPosition,
    include_opportunity: bool = False,
    prediction_service: Any = None,
) -> PositionResponse:
    opportunity: HedgeOpportunitySummary | None = None
    if include_opportunity and position.status == "active":
        raw = HedgeOpportunityDetector.detect(
            session, position, prediction_service=prediction_service
        )
        opportunity = HedgeOpportunitySummary(**raw)
    return PositionResponse(
        id=position.id,
        user_id=position.user_id,
        match_id=position.match_id,
        match_summary=_match_summary(session, position.match_id),
        platform=position.platform,
        market=position.market,  # type: ignore[arg-type]
        outcome=position.outcome,  # type: ignore[arg-type]
        stake=position.stake,
        odds=position.odds,
        placed_at=position.placed_at,
        status=position.status,  # type: ignore[arg-type]
        notes=position.notes,
        created_at=position.created_at,
        updated_at=position.updated_at,
        last_alert_at=position.last_alert_at,
        settlement_pnl=position.settlement_pnl,
        hedge_opportunity=opportunity,
    )


# -----------------------------------------------------------------------------
# Routes
# -----------------------------------------------------------------------------


@router.post("/", response_model=PositionResponse, status_code=status.HTTP_201_CREATED)
def create_position(
    body: CreatePositionRequest,
    session: Session = Depends(get_db_session),
    user_id: int = Depends(_user_id_from_header),
) -> PositionResponse:
    position = PositionService.create(session, user_id, body)
    return _to_response(session, position)


@router.get("/", response_model=list[PositionResponse])
def list_positions(
    position_status: PositionStatus | None = None,
    limit: int = 50,
    session: Session = Depends(get_db_session),
    user_id: int = Depends(_user_id_from_header),
) -> list[PositionResponse]:
    positions = PositionService.list_for_user(
        session, user_id, position_status, min(limit, 200)
    )
    # List endpoint stays cheap — no per-row opportunity check.
    return [_to_response(session, p) for p in positions]


@router.get("/{position_id}", response_model=PositionResponse)
def get_position(
    position_id: int,
    session: Session = Depends(get_db_session),
    user_id: int = Depends(_user_id_from_header),
    prediction_service: Any = Depends(get_prediction_service),
) -> PositionResponse:
    position = PositionService.get_for_user(session, user_id, position_id)
    return _to_response(
        session,
        position,
        include_opportunity=True,
        prediction_service=prediction_service,
    )


@router.patch("/{position_id}/status", response_model=PositionResponse)
def update_position_status(
    position_id: int,
    body: UpdateStatusRequest,
    session: Session = Depends(get_db_session),
    user_id: int = Depends(_user_id_from_header),
) -> PositionResponse:
    position = PositionService.update_status(
        session, user_id, position_id, body.status
    )
    return _to_response(session, position)


@router.delete("/{position_id}", response_model=PositionResponse)
def soft_delete_position(
    position_id: int,
    session: Session = Depends(get_db_session),
    user_id: int = Depends(_user_id_from_header),
) -> PositionResponse:
    position = PositionService.soft_delete(session, user_id, position_id)
    return _to_response(session, position)


@router.post(
    "/{position_id}/check-opportunity",
    response_model=HedgeOpportunitySummary,
)
def check_opportunity(
    position_id: int,
    session: Session = Depends(get_db_session),
    user_id: int = Depends(_user_id_from_header),
    prediction_service: Any = Depends(get_prediction_service),
) -> HedgeOpportunitySummary:
    position = PositionService.get_for_user(session, user_id, position_id)
    raw = HedgeOpportunityDetector.detect(
        session, position, prediction_service=prediction_service
    )
    return HedgeOpportunitySummary(**raw)


__all__ = ["router"]

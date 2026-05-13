"""M10 arbitrage API — opportunity list + per-user watchlist.

  GET    /api/v1/arbitrage/opportunities             list active arbs
  GET    /api/v1/arbitrage/opportunities/{id}        detail
  POST   /api/v1/arbitrage/scan                      admin: trigger now
  GET    /api/v1/arbitrage/watchlist                 caller's rules
  POST   /api/v1/arbitrage/watchlist                 add a rule
  DELETE /api/v1/arbitrage/watchlist/{id}            remove a rule

The opportunity endpoints are public to authed users; the watchlist
endpoints are scoped to the caller (X-User-Id header).
"""
from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from src.api.dependencies import get_db_session
from src.api.schemas.arbitrage import (
    ArbBestQuote,
    ArbOpportunityResponse,
    CreateWatchlistRequest,
    WatchlistResponse,
)
from src.ml.arbitrage.calculator import ArbCalculator
from src.ml.arbitrage.scanner import ArbScanner
from src.models.arbitrage import ArbOpportunity, UserArbWatchlist

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/api/v1/arbitrage", tags=["arbitrage"])


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


def _to_response(opp: ArbOpportunity) -> ArbOpportunityResponse:
    return ArbOpportunityResponse(
        id=opp.id,
        match_id=opp.match_id,
        market_type=opp.market_type,  # type: ignore[arg-type]
        detected_at=opp.detected_at,
        arb_total=opp.arb_total,
        profit_margin=opp.profit_margin,
        best_odds={
            outcome: ArbBestQuote(
                odds=Decimal(str(quote["odds"])),
                bookmaker=quote["bookmaker"],
                captured_at=quote.get("captured_at"),
            )
            for outcome, quote in (opp.best_odds or {}).items()
        },
        stake_distribution={
            outcome: Decimal(str(frac))
            for outcome, frac in (opp.stake_distribution or {}).items()
        },
        status=opp.status,  # type: ignore[arg-type]
        expired_at=opp.expired_at,
    )


# -----------------------------------------------------------------------------
# Opportunities
# -----------------------------------------------------------------------------


@router.get("/opportunities", response_model=list[ArbOpportunityResponse])
def list_opportunities(
    market_type: str | None = Query(default=None),
    min_profit_margin: Decimal | None = Query(default=None, ge=Decimal("0")),
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_db_session),
) -> list[ArbOpportunityResponse]:
    stmt = (
        select(ArbOpportunity)
        .where(ArbOpportunity.status == "active")
        .order_by(desc(ArbOpportunity.profit_margin), desc(ArbOpportunity.detected_at))
        .limit(limit)
    )
    if market_type:
        stmt = stmt.where(ArbOpportunity.market_type == market_type)
    if min_profit_margin is not None:
        stmt = stmt.where(ArbOpportunity.profit_margin >= min_profit_margin)
    rows = list(session.execute(stmt).scalars().all())
    return [_to_response(o) for o in rows]


@router.get("/opportunities/{opportunity_id}", response_model=ArbOpportunityResponse)
def get_opportunity(
    opportunity_id: int,
    session: Session = Depends(get_db_session),
) -> ArbOpportunityResponse:
    opp = session.get(ArbOpportunity, opportunity_id)
    if opp is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"arbitrage opportunity {opportunity_id} not found",
        )
    return _to_response(opp)


@router.post("/scan", status_code=status.HTTP_202_ACCEPTED)
def trigger_scan(
    session: Session = Depends(get_db_session),
) -> dict[str, Any]:
    """Admin path — run a synchronous scan now. The beat-scheduled task
    runs every 60s in production; this endpoint exists for ops + tests."""
    summary = ArbScanner.scan(session)
    return summary


# -----------------------------------------------------------------------------
# Watchlist
# -----------------------------------------------------------------------------


def _watchlist_to_response(row: UserArbWatchlist) -> WatchlistResponse:
    return WatchlistResponse(
        id=row.id,
        user_id=row.user_id,
        competition_id=row.competition_id,
        market_types=row.market_types,
        min_profit_margin=row.min_profit_margin,
        notify_enabled=row.notify_enabled,
        created_at=row.created_at,
    )


@router.get("/watchlist", response_model=list[WatchlistResponse])
def list_watchlist(
    session: Session = Depends(get_db_session),
    user_id: int = Depends(_user_id_from_header),
) -> list[WatchlistResponse]:
    rows = (
        session.execute(
            select(UserArbWatchlist)
            .where(UserArbWatchlist.user_id == user_id)
            .order_by(desc(UserArbWatchlist.created_at))
        )
        .scalars()
        .all()
    )
    return [_watchlist_to_response(r) for r in rows]


@router.post(
    "/watchlist",
    response_model=WatchlistResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_watchlist(
    body: CreateWatchlistRequest,
    session: Session = Depends(get_db_session),
    user_id: int = Depends(_user_id_from_header),
) -> WatchlistResponse:
    row = UserArbWatchlist(
        user_id=user_id,
        competition_id=body.competition_id,
        market_types=body.market_types,
        min_profit_margin=body.min_profit_margin,
        notify_enabled=body.notify_enabled,
    )
    session.add(row)
    session.commit()
    return _watchlist_to_response(row)


@router.delete("/watchlist/{watchlist_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_watchlist(
    watchlist_id: int,
    session: Session = Depends(get_db_session),
    user_id: int = Depends(_user_id_from_header),
) -> None:
    row = session.get(UserArbWatchlist, watchlist_id)
    if row is None or row.user_id != user_id:
        # 404 (not 403) — same existence-leak guard the positions API uses.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"watchlist {watchlist_id} not found",
        )
    session.delete(row)
    session.commit()


__all__ = ["router"]

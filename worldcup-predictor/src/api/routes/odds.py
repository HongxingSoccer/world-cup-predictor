"""POST /api/v1/odds-analysis — compute value signals for a match."""
from __future__ import annotations

from datetime import UTC, datetime
from itertools import groupby

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.api.dependencies import get_db_session, get_prediction_service
from src.api.schemas.odds import (
    OddsAnalysisRequest,
    OddsAnalysisResponse,
    OddsMarketSummary,
    ValueSignal,
)
from src.ml.prediction_service import PredictionService
from src.models.match import Match

router = APIRouter(prefix="/api/v1", tags=["odds"])


@router.post("/odds-analysis", response_model=OddsAnalysisResponse)
def analyze_odds(
    request: OddsAnalysisRequest,
    db_session: Session = Depends(get_db_session),
    service: PredictionService = Depends(get_prediction_service),
) -> OddsAnalysisResponse:
    """Generate a transient prediction + value-analysis report for `match_id`.

    The endpoint does not persist anything: the request is read-only by
    design. To persist, call `/predict` with `publish=true` first; that
    stores both the prediction and its odds analysis.
    """
    match = db_session.get(Match, request.match_id)
    if match is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"match {request.match_id} not found",
        )

    full = service.generate_prediction(request.match_id, publish=False)

    # Reuse the odds analyzer attached to the service (transient mode).
    raw = service._odds.analyze_match(request.match_id, full.prediction)
    raw = _filter_request(raw, request)

    signals = [
        ValueSignal(
            market_type=r.market_type,
            market_value=r.market_value,
            outcome=r.outcome,
            model_prob=r.model_prob,
            best_odds=r.best_odds,
            best_bookmaker=r.best_bookmaker,
            implied_prob=r.implied_prob,
            ev=r.ev,
            edge=r.edge,
            signal_level=r.signal_level,
        )
        for r in raw
    ]

    # Group per market for the structured response.
    grouped = sorted(signals, key=lambda s: (s.market_type, s.market_value or ""))
    markets = [
        OddsMarketSummary(market_type=key[0], market_value=key[1] or None, outcomes=list(group))
        for key, group in groupby(grouped, key=lambda s: (s.market_type, s.market_value or ""))
    ]

    value_signals = sorted(
        (s for s in signals if s.signal_level >= 1),
        key=lambda s: -s.ev,
    )

    return OddsAnalysisResponse(
        match_id=match.id,
        analysis_time=datetime.now(UTC),
        markets=markets,
        value_signals=value_signals,
    )


def _filter_request(results, request: OddsAnalysisRequest):  # type: ignore[no-untyped-def]
    """Drop markets / bookmakers that the caller didn't ask for."""
    market_filter = _normalise_markets(request.markets)
    out = []
    for r in results:
        bucket = _market_bucket(r.market_type, r.market_value)
        if market_filter and bucket not in market_filter:
            continue
        if request.bookmakers and r.best_bookmaker not in request.bookmakers:
            continue
        out.append(r)
    return out


def _normalise_markets(markets: list[str]) -> set[str]:
    """Translate human-friendly market labels into the storage vocabulary."""
    out: set[str] = set()
    for label in markets:
        token = label.strip().lower()
        if token == "1x2":
            out.add("1x2")
        elif token.startswith("over_under"):
            # Accept "over_under" or "over_under_2.5".
            out.add(token if token != "over_under" else "over_under_2.5")
        elif token == "btts":
            out.add("btts")
    return out


def _market_bucket(market_type: str, market_value: str | None) -> str:
    if market_type == "over_under":
        return f"over_under_{market_value}"
    return market_type

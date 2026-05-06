"""GET /api/v1/predictions/today  +  GET /api/v1/predictions/{id}.

Both endpoints read from the persisted `predictions` table. /today is cached
in Redis for `PREDICTIONS_TODAY_CACHE_TTL` seconds; /{id} is uncached because
the table is immutable so the response can be served directly via the CDN.
"""
from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.dependencies import (
    get_db_session,
    get_redis,
    predictions_today_cache_ttl,
)
from src.api.schemas.predictions import (
    PredictionDetailResponse,
    PredictionTodayItem,
    PredictionTodayResponse,
    PredictionUpcomingResponse,
)
from src.models.match import Match
from src.models.odds_analysis import OddsAnalysis
from src.models.prediction import Prediction
from src.models.season import Season
from src.models.team import Team

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/v1/predictions", tags=["predictions"])

CACHE_KEY_PREFIX: str = "wcp:predictions:today"


@router.get("/today", response_model=PredictionTodayResponse)
def predictions_today(
    target_date: Optional[date] = Query(default=None, alias="date"),
    min_confidence: int = Query(default=0, ge=0, le=100),
    min_signal: int = Query(default=0, ge=0, le=3),
    competition_id: Optional[int] = Query(default=None),
    db_session: Session = Depends(get_db_session),
    redis_client: Optional[Any] = Depends(get_redis),
    cache_ttl: int = Depends(predictions_today_cache_ttl),
) -> PredictionTodayResponse:
    """Return all matches with predictions for `date` (default = today UTC)."""
    target = target_date or datetime.now(timezone.utc).date()
    cache_key = (
        f"{CACHE_KEY_PREFIX}:{target.isoformat()}"
        f":mc{min_confidence}:ms{min_signal}:c{competition_id or 'all'}"
    )

    cached = _try_cache_read(redis_client, cache_key)
    if cached is not None:
        return PredictionTodayResponse.model_validate({**cached, "cached": True})

    items = _fetch_today_items(
        db_session,
        target,
        min_confidence=min_confidence,
        min_signal=min_signal,
        competition_id=competition_id,
    )
    response = PredictionTodayResponse(date=target.isoformat(), items=items, cached=False)
    _try_cache_write(redis_client, cache_key, response, cache_ttl)
    return response


@router.get("/upcoming", response_model=PredictionUpcomingResponse)
def predictions_upcoming(
    days: int = Query(default=60, ge=1, le=180),
    min_confidence: int = Query(default=0, ge=0, le=100),
    db_session: Session = Depends(get_db_session),
) -> PredictionUpcomingResponse:
    """Return predictions for every scheduled match kicking off in the next ``days``.

    Drives the homepage 'upcoming matches' module — orders by kickoff so the
    client can group by date with a single pass. No Redis cache: the result
    rolls forward every day and the underlying query is small (≤ 100 rows
    in practice).
    """
    now = datetime.now(timezone.utc)
    end = now + timedelta(days=days)

    HomeTeam = Team.__table__.alias("home_team")  # noqa: N806
    AwayTeam = Team.__table__.alias("away_team")  # noqa: N806

    stmt = (
        select(
            Prediction.id,
            Prediction.match_id,
            Prediction.prob_home_win,
            Prediction.prob_draw,
            Prediction.prob_away_win,
            Prediction.confidence_score,
            Prediction.confidence_level,
            Match.match_date,
            HomeTeam.c.name.label("home_team"),
            AwayTeam.c.name.label("away_team"),
            Season.year,
        )
        .join(Match, Match.id == Prediction.match_id)
        .join(HomeTeam, HomeTeam.c.id == Match.home_team_id)
        .join(AwayTeam, AwayTeam.c.id == Match.away_team_id)
        .join(Season, Season.id == Match.season_id)
        .where(
            Match.match_date >= now,
            Match.match_date < end,
            Match.status == "scheduled",
            Prediction.confidence_score >= min_confidence,
        )
        .order_by(Match.match_date)
    )
    rows = db_session.execute(stmt).all()

    pred_ids = [row.id for row in rows]
    sig_levels: dict[int, int] = {}
    if pred_ids:
        sig_levels = dict(
            db_session.execute(
                select(OddsAnalysis.prediction_id, OddsAnalysis.signal_level)
                .where(OddsAnalysis.prediction_id.in_(pred_ids))
                .order_by(OddsAnalysis.signal_level.desc())
            ).all()
        )

    items = [
        PredictionTodayItem(
            match_id=row.match_id,
            match_date=row.match_date,
            home_team=row.home_team,
            away_team=row.away_team,
            competition=str(row.year) if row.year else None,
            prob_home_win=float(row.prob_home_win),
            prob_draw=float(row.prob_draw),
            prob_away_win=float(row.prob_away_win),
            confidence_score=int(row.confidence_score),
            confidence_level=row.confidence_level,
            top_signal_level=int(sig_levels.get(row.id, 0)),
        )
        for row in rows
    ]
    return PredictionUpcomingResponse(days_ahead=days, items=items)


@router.get("/{prediction_id}", response_model=PredictionDetailResponse)
def prediction_detail(
    prediction_id: int,
    db_session: Session = Depends(get_db_session),
) -> PredictionDetailResponse:
    """Return one prediction's full body plus its associated odds_analysis rows."""
    pred = db_session.get(Prediction, prediction_id)
    if pred is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"prediction {prediction_id} not found",
        )

    analysis_rows = db_session.execute(
        select(OddsAnalysis).where(OddsAnalysis.prediction_id == prediction_id)
    ).scalars().all()

    return PredictionDetailResponse(
        prediction_id=pred.id,
        match_id=pred.match_id,
        model_version=pred.model_version,
        feature_version=pred.feature_version,
        published_at=pred.published_at,
        prob_home_win=float(pred.prob_home_win),
        prob_draw=float(pred.prob_draw),
        prob_away_win=float(pred.prob_away_win),
        lambda_home=float(pred.lambda_home),
        lambda_away=float(pred.lambda_away),
        btts_prob=float(pred.btts_prob) if pred.btts_prob is not None else None,
        score_matrix=pred.score_matrix,
        top_scores=pred.top_scores,
        over_under_probs=pred.over_under_probs,
        confidence_score=pred.confidence_score,
        confidence_level=pred.confidence_level,
        content_hash=pred.content_hash,
        features_snapshot=pred.features_snapshot,
        odds_analysis=[_row_to_dict(row) for row in analysis_rows],
    )


# --- Internal helpers ---


def _fetch_today_items(
    db_session: Session,
    target: date,
    *,
    min_confidence: int,
    min_signal: int,
    competition_id: Optional[int],
) -> list[PredictionTodayItem]:
    start = datetime.combine(target, time.min, tzinfo=timezone.utc)
    end = start + timedelta(days=1)

    HomeTeam = Team.__table__.alias("home_team")  # noqa: N806
    AwayTeam = Team.__table__.alias("away_team")  # noqa: N806

    stmt = (
        select(
            Prediction.id,
            Prediction.match_id,
            Prediction.prob_home_win,
            Prediction.prob_draw,
            Prediction.prob_away_win,
            Prediction.confidence_score,
            Prediction.confidence_level,
            Match.match_date,
            HomeTeam.c.name.label("home_team"),
            AwayTeam.c.name.label("away_team"),
            Season.year,
        )
        .join(Match, Match.id == Prediction.match_id)
        .join(HomeTeam, HomeTeam.c.id == Match.home_team_id)
        .join(AwayTeam, AwayTeam.c.id == Match.away_team_id)
        .join(Season, Season.id == Match.season_id)
        .where(
            Match.match_date >= start,
            Match.match_date < end,
            Prediction.confidence_score >= min_confidence,
        )
        .order_by(Match.match_date)
    )
    if competition_id is not None:
        stmt = stmt.where(Season.competition_id == competition_id)

    rows = db_session.execute(stmt).all()
    if not rows:
        return []

    # Compute the highest signal_level per prediction; cheap because the
    # odds_analysis table is small relative to predictions.
    pred_ids = [row.id for row in rows]
    sig_levels = dict(
        db_session.execute(
            select(OddsAnalysis.prediction_id, OddsAnalysis.signal_level)
            .where(OddsAnalysis.prediction_id.in_(pred_ids))
            .order_by(OddsAnalysis.signal_level.desc())
        ).all()
    )

    out: list[PredictionTodayItem] = []
    for row in rows:
        top_signal = int(sig_levels.get(row.id, 0))
        if top_signal < min_signal:
            continue
        out.append(
            PredictionTodayItem(
                match_id=row.match_id,
                match_date=row.match_date,
                home_team=row.home_team,
                away_team=row.away_team,
                competition=str(row.year) if row.year else None,
                prob_home_win=float(row.prob_home_win),
                prob_draw=float(row.prob_draw),
                prob_away_win=float(row.prob_away_win),
                confidence_score=int(row.confidence_score),
                confidence_level=row.confidence_level,
                top_signal_level=top_signal,
            )
        )
    return out


def _row_to_dict(row: OddsAnalysis) -> dict[str, Any]:
    return {
        "id": row.id,
        "market_type": row.market_type,
        "market_value": row.market_value,
        "outcome": row.outcome,
        "model_prob": float(row.model_prob),
        "best_odds": float(row.best_odds),
        "best_bookmaker": row.best_bookmaker,
        "implied_prob": float(row.implied_prob),
        "ev": float(row.ev),
        "edge": float(row.edge),
        "signal_level": int(row.signal_level),
    }


def _try_cache_read(redis_client: Optional[Any], key: str) -> Optional[dict[str, Any]]:
    if redis_client is None:
        return None
    try:
        raw = redis_client.get(key)
    except Exception as exc:
        logger.warning("redis_read_failed", key=key, error=str(exc))
        return None
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def _try_cache_write(
    redis_client: Optional[Any],
    key: str,
    response: PredictionTodayResponse,
    ttl: int,
) -> None:
    if redis_client is None or ttl <= 0:
        return
    try:
        redis_client.setex(key, ttl, response.model_dump_json())
    except Exception as exc:
        logger.warning("redis_write_failed", key=key, error=str(exc))

"""Public scoreboard endpoints — read from `track_record_stats` and
`prediction_results` without ever recomputing.

Returns zero-valued defaults instead of 404 when the underlying tables are
empty (pre-tournament, before any settlement runs). The frontend renders a
"data will land once the tournament starts" empty state in that case rather
than a broken page.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import asc, select
from sqlalchemy.orm import Session

from src.api.dependencies import get_db_session
from src.models.prediction_result import PredictionResult
from src.models.track_record_stat import TrackRecordStat
from src.utils.track_record import PERIODS, STAT_TYPES

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/v1/track-record", tags=["track-record"])


class TrackRecordOverview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stat_type: str
    period: str
    total_predictions: int
    hits: int
    hit_rate: float
    total_pnl_units: float
    roi: float
    current_streak: int
    best_streak: int
    updated_at: Optional[datetime] = None


class RoiPoint(BaseModel):
    """One day on the cumulative-ROI line chart."""

    model_config = ConfigDict(extra="forbid")

    date: str  # YYYY-MM-DD
    cumulative_pnl: float
    cumulative_roi: float
    settled_count: int


class RoiTimeseries(BaseModel):
    model_config = ConfigDict(extra="forbid")

    period: str
    points: list[RoiPoint] = Field(default_factory=list)


@router.get("/overview", response_model=TrackRecordOverview)
def overview(
    stat_type: str = Query(default="overall", alias="statType"),
    period: str = Query(default="all_time"),
    db_session: Session = Depends(get_db_session),
) -> TrackRecordOverview:
    """Return one (statType, period) row, or a zero-default if missing."""
    if stat_type not in STAT_TYPES:
        stat_type = "overall"
    if period not in PERIODS:
        period = "all_time"

    row = db_session.execute(
        select(TrackRecordStat).where(
            TrackRecordStat.stat_type == stat_type,
            TrackRecordStat.period == period,
        )
    ).scalar_one_or_none()
    if row is None:
        return _zero_overview(stat_type, period)
    return _row_to_overview(row)


@router.get("/roi-chart", response_model=list[TrackRecordOverview])
def roi_chart(
    period: str = Query(default="all_time"),
    db_session: Session = Depends(get_db_session),
) -> list[TrackRecordOverview]:
    """Return every stat-type row for the given period.

    Backs the per-market breakdown card; when the table is empty we return
    one zero-row per known stat type so the frontend's table still renders
    its skeleton.
    """
    if period not in PERIODS:
        period = "all_time"

    rows = (
        db_session.execute(
            select(TrackRecordStat).where(TrackRecordStat.period == period)
        )
        .scalars()
        .all()
    )
    if not rows:
        return [_zero_overview(st, period) for st in STAT_TYPES]

    by_type = {row.stat_type: row for row in rows}
    return [
        _row_to_overview(by_type[st]) if st in by_type else _zero_overview(st, period)
        for st in STAT_TYPES
    ]


@router.get("/timeseries", response_model=RoiTimeseries)
def timeseries(
    period: str = Query(default="all_time"),
    db_session: Session = Depends(get_db_session),
) -> RoiTimeseries:
    """Daily cumulative P&L + cumulative ROI from settled prediction_results."""
    if period not in PERIODS:
        period = "all_time"

    cutoff = _period_cutoff(period)
    stmt = select(PredictionResult).order_by(asc(PredictionResult.settled_at))
    if cutoff is not None:
        stmt = stmt.where(PredictionResult.settled_at >= cutoff)

    settled = db_session.execute(stmt).scalars().all()
    if not settled:
        return RoiTimeseries(period=period, points=[])

    by_day: dict[date, dict[str, float]] = {}
    for r in settled:
        day = r.settled_at.date() if r.settled_at else None
        if day is None:
            continue
        bucket = by_day.setdefault(day, {"pnl": 0.0, "count": 0})
        if r.pnl_unit is not None:
            bucket["pnl"] += float(r.pnl_unit)
        bucket["count"] += 1

    points: list[RoiPoint] = []
    cumulative_pnl = 0.0
    cumulative_count = 0
    for day in sorted(by_day):
        cumulative_pnl += by_day[day]["pnl"]
        cumulative_count += int(by_day[day]["count"])
        roi = cumulative_pnl / cumulative_count if cumulative_count else 0.0
        points.append(
            RoiPoint(
                date=day.isoformat(),
                cumulative_pnl=round(cumulative_pnl, 4),
                cumulative_roi=round(roi, 4),
                settled_count=cumulative_count,
            )
        )
    return RoiTimeseries(period=period, points=points)


# --- Helpers --------------------------------------------------------------


def _row_to_overview(row: TrackRecordStat) -> TrackRecordOverview:
    return TrackRecordOverview(
        stat_type=row.stat_type,
        period=row.period,
        total_predictions=int(row.total_predictions),
        hits=int(row.hits),
        hit_rate=float(row.hit_rate or Decimal("0")),
        total_pnl_units=float(row.total_pnl_units or Decimal("0")),
        roi=float(row.roi or Decimal("0")),
        current_streak=int(row.current_streak),
        best_streak=int(row.best_streak),
        updated_at=row.updated_at,
    )


def _zero_overview(stat_type: str, period: str) -> TrackRecordOverview:
    return TrackRecordOverview(
        stat_type=stat_type,
        period=period,
        total_predictions=0,
        hits=0,
        hit_rate=0.0,
        total_pnl_units=0.0,
        roi=0.0,
        current_streak=0,
        best_streak=0,
        updated_at=None,
    )


def _period_cutoff(period: str) -> Optional[datetime]:
    from datetime import timedelta

    from src.utils.track_record import WORLDCUP_2026_START

    now = datetime.now(timezone.utc)
    if period == "all_time":
        return None
    if period == "last_30d":
        return now - timedelta(days=30)
    if period == "last_7d":
        return now - timedelta(days=7)
    if period == "worldcup":
        return WORLDCUP_2026_START
    return None

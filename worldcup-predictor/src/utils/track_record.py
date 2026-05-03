"""Track-record aggregation: roll up `prediction_results` rows into the cached
`track_record_stats` matrix (6 stat-types × 4 periods).

Pure-Python / pure-DB code: the Celery task in
`src.tasks.settlement_tasks` calls `recompute_all(session)` after every
settlement to keep `track_record_stats` warm, so the public scoreboard can
serve directly from the cache row.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import structlog
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from src.models.prediction_result import PredictionResult
from src.models.track_record_stat import TrackRecordStat
from src.utils.settlement import compute_streaks

logger = structlog.get_logger(__name__)

STAT_TYPES: tuple[str, ...] = (
    "overall",
    "1x2",
    "score",
    "ou25",
    "btts",
    "positive_ev",
)
PERIODS: tuple[str, ...] = ("all_time", "last_30d", "last_7d", "worldcup")

# Phase-3 placeholder: real WC2026 dates land closer to the tournament.
# Update via env / config when fixtures finalise.
WORLDCUP_2026_START: datetime = datetime(2026, 6, 11, tzinfo=timezone.utc)
WORLDCUP_2026_END: datetime = datetime(2026, 7, 19, 23, 59, 59, tzinfo=timezone.utc)


@dataclass(frozen=True)
class StatBreakdown:
    """Aggregate metrics for one (stat_type, period) cell."""

    total_predictions: int
    hits: int
    hit_rate: Decimal
    total_pnl_units: Decimal
    roi: Decimal
    current_streak: int
    best_streak: int


# --- Public API -----------------------------------------------------------


def recompute_all(session: Session, *, now: datetime | None = None) -> int:
    """Recompute every (stat_type, period) cell and upsert into `track_record_stats`.

    Returns the count of rows touched (always 24 — one per cell).
    """
    when = now or datetime.now(timezone.utc)
    rows = _load_settled_rows(session)

    written = 0
    for stat_type in STAT_TYPES:
        for period in PERIODS:
            window = _filter_for(rows, stat_type, period, when)
            breakdown = _aggregate(window, stat_type)
            _upsert(session, stat_type, period, breakdown)
            written += 1
    session.commit()
    logger.info("track_record_recomputed", rows=written, source_rows=len(rows))
    return written


# --- Aggregation core (pure functions, easy to test) ---------------------


def aggregate(rows: list[PredictionResult], stat_type: str) -> StatBreakdown:
    """Compute the aggregate metrics for the given (already-filtered) rows."""
    return _aggregate(rows, stat_type)


def _aggregate(rows: list[PredictionResult], stat_type: str) -> StatBreakdown:
    """Pure aggregator. Returns zero metrics on empty input rather than NaN."""
    if not rows:
        return StatBreakdown(
            total_predictions=0,
            hits=0,
            hit_rate=Decimal("0"),
            total_pnl_units=Decimal("0"),
            roi=Decimal("0"),
            current_streak=0,
            best_streak=0,
        )

    # Sort chronologically once — used by both the streak walk and the
    # "current" series at the bottom of the response.
    ordered = sorted(rows, key=lambda r: r.settled_at)

    if stat_type == "positive_ev":
        # Only rows where a real bet would have been placed contribute.
        bet_rows = [r for r in ordered if r.best_ev_outcome is not None]
        total = len(bet_rows)
        hits = sum(1 for r in bet_rows if r.best_ev_hit)
        pnl_total = sum((r.pnl_unit or Decimal("0")) for r in bet_rows)
        # ROI for positive-EV bets: total PnL / total stakes (1 per row).
        roi = (pnl_total / Decimal(total)) if total else Decimal("0")
        current_streak, best_streak = compute_streaks(bool(r.best_ev_hit) for r in bet_rows)
        return StatBreakdown(
            total_predictions=total,
            hits=hits,
            hit_rate=_pct(hits, total),
            total_pnl_units=pnl_total,
            roi=roi.quantize(Decimal("0.0001")),
            current_streak=current_streak,
            best_streak=best_streak,
        )

    hit_picker = _hit_picker(stat_type)
    # Drop rows where the hit value is intentionally null (e.g. ou25 when the
    # original prediction didn't ship the OU market).
    eligible = [(r, hit_picker(r)) for r in ordered]
    eligible = [(r, hit) for r, hit in eligible if hit is not None]
    total = len(eligible)
    hits = sum(1 for _, hit in eligible if hit)
    pnl_total = sum((r.pnl_unit or Decimal("0")) for r, _ in eligible)
    roi = (pnl_total / Decimal(total)) if total else Decimal("0")
    current_streak, best_streak = compute_streaks(bool(hit) for _, hit in eligible)
    return StatBreakdown(
        total_predictions=total,
        hits=hits,
        hit_rate=_pct(hits, total),
        total_pnl_units=pnl_total,
        roi=roi.quantize(Decimal("0.0001")),
        current_streak=current_streak,
        best_streak=best_streak,
    )


# --- Filters --------------------------------------------------------------


def _filter_for(
    rows: list[PredictionResult],
    stat_type: str,
    period: str,
    now: datetime,
) -> list[PredictionResult]:
    """Apply the period filter (stat_type-level filter happens inside _aggregate).

    SQLite drops tzinfo on round-trip. We coerce every `settled_at` to UTC-aware
    before comparing against the (always-aware) period bounds — Postgres
    preserves the tz natively, so the coercion is a no-op there.
    """
    cutoff = _period_lower_bound(period, now)
    if cutoff is None and period != "worldcup":
        return rows
    if period == "worldcup":
        return [
            r for r in rows
            if WORLDCUP_2026_START <= _ensure_utc(r.settled_at) <= WORLDCUP_2026_END
        ]
    return [r for r in rows if _ensure_utc(r.settled_at) >= cutoff]


def _ensure_utc(value: datetime) -> datetime:
    """Treat naive datetimes as UTC (the project's storage convention)."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _period_lower_bound(period: str, now: datetime) -> datetime | None:
    if period == "all_time":
        return None
    if period == "last_30d":
        return now - timedelta(days=30)
    if period == "last_7d":
        return now - timedelta(days=7)
    if period == "worldcup":
        return WORLDCUP_2026_START
    raise ValueError(f"unknown period: {period}")


# --- Stat-type adapters ---------------------------------------------------


def _hit_picker(stat_type: str):  # type: ignore[no-untyped-def]
    """Return a callable that, given a `PredictionResult`, returns its hit bool."""
    if stat_type == "overall":
        return lambda r: r.result_1x2_hit
    if stat_type == "1x2":
        return lambda r: r.result_1x2_hit
    if stat_type == "score":
        return lambda r: r.result_score_hit
    if stat_type == "ou25":
        return lambda r: r.result_ou25_hit
    if stat_type == "btts":
        return lambda r: r.result_btts_hit
    raise ValueError(f"unknown stat_type: {stat_type}")


# --- DB I/O ----------------------------------------------------------------


def _load_settled_rows(session: Session) -> list[PredictionResult]:
    return list(session.execute(select(PredictionResult)).scalars().all())


def _upsert(
    session: Session,
    stat_type: str,
    period: str,
    breakdown: StatBreakdown,
) -> None:
    stmt = pg_insert(TrackRecordStat).values(
        stat_type=stat_type,
        period=period,
        total_predictions=breakdown.total_predictions,
        hits=breakdown.hits,
        hit_rate=breakdown.hit_rate,
        total_pnl_units=breakdown.total_pnl_units,
        roi=breakdown.roi,
        current_streak=breakdown.current_streak,
        best_streak=breakdown.best_streak,
    )
    update_cols = {
        col.name: stmt.excluded[col.name]
        for col in TrackRecordStat.__table__.columns
        if col.name not in {"id", "stat_type", "period"}
    }
    session.execute(
        stmt.on_conflict_do_update(
            constraint="uq_track_stats_type_period",
            set_=update_cols,
        )
    )


def _pct(numerator: int, denominator: int) -> Decimal:
    if denominator == 0:
        return Decimal("0")
    return (Decimal(numerator) / Decimal(denominator)).quantize(Decimal("0.0001"))

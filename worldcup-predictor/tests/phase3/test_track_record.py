"""Unit tests for the track-record aggregator (`src.utils.track_record`)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from src.models.prediction_result import PredictionResult
from src.utils.track_record import (
    StatBreakdown,
    WORLDCUP_2026_END,
    WORLDCUP_2026_START,
    aggregate,
    recompute_all,
)


def _row(
    *,
    settled_at: datetime,
    one_x_two: bool,
    score_hit: bool = False,
    ou25_hit: bool | None = None,
    btts_hit: bool | None = None,
    best_ev_outcome: str | None = None,
    best_ev_hit: bool | None = None,
    pnl: Decimal = Decimal("0"),
    prediction_id: int = 1,
) -> PredictionResult:
    return PredictionResult(
        prediction_id=prediction_id,
        match_id=prediction_id,
        actual_home_score=1,
        actual_away_score=0,
        result_1x2_hit=one_x_two,
        result_score_hit=score_hit,
        result_ou25_hit=ou25_hit,
        result_btts_hit=btts_hit,
        best_ev_outcome=best_ev_outcome,
        best_ev_odds=Decimal("2.10") if best_ev_outcome else None,
        best_ev_hit=best_ev_hit,
        pnl_unit=pnl,
        settled_at=settled_at,
    )


# --- aggregate(): pure math ----------------------------------------------


def test_aggregate_overall_handles_basic_hit_rate():
    now = datetime(2026, 5, 1, tzinfo=timezone.utc)
    # `aggregate` sorts by settled_at ASC. Chronologically:
    #   day-4 (hit), day-3 (miss), day-2 (hit), day-1 (hit).
    # Streak walk: 1, -1, 1, 2 → current=2, best=2.
    rows = [
        _row(settled_at=now - timedelta(days=1), one_x_two=True),
        _row(settled_at=now - timedelta(days=2), one_x_two=True),
        _row(settled_at=now - timedelta(days=3), one_x_two=False),
        _row(settled_at=now - timedelta(days=4), one_x_two=True),
    ]
    result = aggregate(rows, "overall")
    assert result.total_predictions == 4
    assert result.hits == 3
    assert result.hit_rate == Decimal("0.7500")
    assert result.current_streak == 2
    assert result.best_streak == 2


def test_aggregate_skips_rows_with_none_hit_for_typed_markets():
    now = datetime(2026, 5, 1, tzinfo=timezone.utc)
    rows = [
        _row(settled_at=now, one_x_two=True, ou25_hit=True),
        _row(settled_at=now + timedelta(hours=1), one_x_two=False, ou25_hit=None),
        _row(settled_at=now + timedelta(hours=2), one_x_two=True, ou25_hit=False),
    ]
    result = aggregate(rows, "ou25")
    # Only two rows had a non-null OU25 verdict.
    assert result.total_predictions == 2
    assert result.hits == 1
    assert result.hit_rate == Decimal("0.5000")


def test_aggregate_positive_ev_uses_best_ev_outcome_filter():
    now = datetime(2026, 5, 1, tzinfo=timezone.utc)
    rows = [
        _row(
            settled_at=now,
            one_x_two=True,
            best_ev_outcome="home",
            best_ev_hit=True,
            pnl=Decimal("1.10"),
        ),
        _row(
            settled_at=now + timedelta(hours=1),
            one_x_two=False,
            best_ev_outcome="away",
            best_ev_hit=False,
            pnl=Decimal("-1.00"),
        ),
        # No bet placed → excluded from positive_ev aggregate.
        _row(settled_at=now + timedelta(hours=2), one_x_two=True),
    ]
    result = aggregate(rows, "positive_ev")
    assert result.total_predictions == 2
    assert result.hits == 1
    assert result.total_pnl_units == Decimal("0.10")
    assert result.roi == Decimal("0.0500")


def test_aggregate_returns_zero_breakdown_for_empty_input():
    result = aggregate([], "overall")
    assert result == StatBreakdown(
        total_predictions=0,
        hits=0,
        hit_rate=Decimal("0"),
        total_pnl_units=Decimal("0"),
        roi=Decimal("0"),
        current_streak=0,
        best_streak=0,
    )


# --- recompute_all(): writes the 24-cell matrix --------------------------


def test_recompute_all_writes_full_matrix(db_session):
    # Seed three settled predictions split across periods.
    now = datetime(2026, 5, 1, tzinfo=timezone.utc)
    db_session.add_all([
        _row(prediction_id=10, settled_at=now - timedelta(days=2), one_x_two=True),
        _row(prediction_id=11, settled_at=now - timedelta(days=4), one_x_two=False),
        _row(prediction_id=12, settled_at=now - timedelta(days=20), one_x_two=True),
    ])
    db_session.commit()

    written = recompute_all(db_session, now=now)
    # 6 stat_types × 4 periods = 24 cells regardless of input size.
    assert written == 24


def test_recompute_all_period_filter_isolates_worldcup_window(db_session):
    in_window = WORLDCUP_2026_START + timedelta(days=3)
    out_of_window = WORLDCUP_2026_START - timedelta(days=10)

    db_session.add_all([
        _row(prediction_id=20, settled_at=in_window, one_x_two=True),
        _row(prediction_id=21, settled_at=out_of_window, one_x_two=False),
    ])
    db_session.commit()

    recompute_all(db_session, now=in_window + timedelta(days=1))

    from src.models.track_record_stat import TrackRecordStat

    wc_overall = (
        db_session.query(TrackRecordStat)
        .filter(
            TrackRecordStat.stat_type == "overall",
            TrackRecordStat.period == "worldcup",
        )
        .one()
    )
    # Only the in-window row is counted under the WC period.
    assert wc_overall.total_predictions == 1
    assert wc_overall.hits == 1


@pytest.mark.parametrize("period", ["all_time", "last_30d", "last_7d", "worldcup"])
def test_recompute_all_emits_one_row_per_period(db_session, period):
    db_session.commit()  # Ensure clean state on the (transactional) test session.
    recompute_all(db_session, now=datetime(2026, 5, 1, tzinfo=timezone.utc))

    from src.models.track_record_stat import TrackRecordStat

    rows = (
        db_session.query(TrackRecordStat)
        .filter(TrackRecordStat.period == period)
        .all()
    )
    # 6 stat_types per period.
    assert len(rows) == 6

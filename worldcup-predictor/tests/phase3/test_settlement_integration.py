"""Integration coverage for the settlement Celery task.

The existing settlement tests in this directory pin the pure-math helpers
(`is_1x2_hit`, `evaluate_best_ev`, etc.) — but nothing exercises the
orchestrator that's actually scheduled by Beat. This file fills that gap:
we drive `_settle_match` against the SQLite in-memory test DB, monkeypatch
the production `session_scope` to use the same engine, and stub out the
two side-effects we don't want firing in unit tests (Kafka producer +
Celery `send_task` for the red-hit card fanout).

What we pin:
* The transaction actually inserts a `prediction_results` row with the
  correct hit flags + EV pnl.
* Re-running the task on a fully-settled match is a no-op (idempotency).
* `track_record_stats` are recomputed when at least one prediction
  settles in the call.
* The scanner only dispatches matches that finished long enough ago AND
  still have an un-settled prediction.
* Matches with NULL scores (status flipped to finished but the data feed
  hasn't shipped the scoreline yet) are skipped gracefully.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Iterator

import pytest
from sqlalchemy.orm import Session

from src.models.match import Match
from src.models.odds_analysis import OddsAnalysis
from src.models.prediction import Prediction
from src.models.prediction_result import PredictionResult
from src.models.track_record_stat import TrackRecordStat
from src.tasks import settlement_tasks


# ---------------------------------------------------------------------------
# Test infrastructure
# ---------------------------------------------------------------------------


@pytest.fixture()
def patched_session(monkeypatch: pytest.MonkeyPatch, db_session: Session):
    """Route the task's `session_scope()` to the SQLite test session.

    The production scope opens its own Session against the real Postgres
    DSN and commits at exit. For the test we want both halves of the test
    transaction to live in the same in-memory session, so we yield it
    without committing — the conftest fixture rolls back at teardown.
    """

    @contextmanager
    def _scope() -> Iterator[Session]:
        # Flushing is enough for downstream reads inside the same session;
        # the fixture rolls back at the end, so a real commit would just
        # poison the next test.
        yield db_session

    monkeypatch.setattr(settlement_tasks, "session_scope", _scope)
    return db_session


@pytest.fixture(autouse=True)
def _silence_side_effects(monkeypatch: pytest.MonkeyPatch):
    """No-op the Kafka producer + Redis cache scan + Celery dispatch.

    Without this the task tries to open a Kafka producer at module import
    and call `app.send_task` for the red-hit card fanout, both of which
    would fail outside a running stack.
    """
    class _NullProducer:
        def publish(self, **_kw):
            return None

        def close(self) -> None:
            return None

    monkeypatch.setattr(settlement_tasks, "build_producer", lambda: _NullProducer())
    monkeypatch.setattr(settlement_tasks, "_invalidate_caches", lambda: None)

    sent: list[tuple[str, list]] = []

    def _record_send(name: str, args=None, **_kw):
        sent.append((name, list(args or [])))

    monkeypatch.setattr(settlement_tasks.app, "send_task", _record_send)
    return sent


# ---------------------------------------------------------------------------
# Match fixtures
# ---------------------------------------------------------------------------


def _finished_match(make_match, utc, *, kickoff=None, home_score=2, away_score=1) -> Match:
    """Finished 2026-05-01 match by default — comfortably past the 2h cutoff."""
    kickoff = kickoff or utc(2026, 5, 1, 18)
    return make_match(kickoff, home_score=home_score, away_score=away_score, status="finished")


def _insert_prediction(
    session: Session,
    match_id: int,
    *,
    prob_home: float = 0.62,
    prob_draw: float = 0.22,
    prob_away: float = 0.16,
    top_scores: list[dict] | None = None,
    btts_prob: float = 0.55,
    ou25_over: float = 0.55,
) -> Prediction:
    pred = Prediction(
        match_id=match_id,
        model_version="poisson_v1",
        feature_version="v1",
        prob_home_win=Decimal(str(prob_home)),
        prob_draw=Decimal(str(prob_draw)),
        prob_away_win=Decimal(str(prob_away)),
        lambda_home=Decimal("1.8"),
        lambda_away=Decimal("0.9"),
        score_matrix=[[0.05] * 10] * 10,
        top_scores=top_scores or [
            {"score": "2-1", "prob": 0.10},
            {"score": "1-0", "prob": 0.09},
            {"score": "1-1", "prob": 0.08},
        ],
        over_under_probs={
            "2.5": {"over": ou25_over, "under": 1 - ou25_over},
            "1.5": {"over": 0.75, "under": 0.25},
            "3.5": {"over": 0.25, "under": 0.75},
        },
        btts_prob=Decimal(str(btts_prob)),
        confidence_score=75,
        confidence_level="high",
        features_snapshot={},
        content_hash="x" * 64,
        published_at=datetime.now(timezone.utc),
    )
    session.add(pred)
    session.flush()
    return pred


def _insert_value_signal(
    session: Session,
    *,
    match_id: int,
    prediction_id: int,
    outcome: str,
    odds: float,
    signal_level: int = 2,
    market_type: str = "1x2",
    ev: float = 0.15,
) -> OddsAnalysis:
    row = OddsAnalysis(
        match_id=match_id,
        prediction_id=prediction_id,
        market_type=market_type,
        market_value=None,
        outcome=outcome,
        model_prob=Decimal("0.62"),
        best_odds=Decimal(str(odds)),
        best_bookmaker="testmaker",
        implied_prob=Decimal(str(round(1 / odds, 4))),
        ev=Decimal(str(ev)),
        edge=Decimal("0.05"),
        signal_level=signal_level,
        analyzed_at=datetime.now(timezone.utc),
    )
    session.add(row)
    session.flush()
    return row


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_settle_match_writes_full_verdict(patched_session, make_match, utc):
    """Happy path: home win predicted, top-scoring 2-1 in top_scores, value signal on home.

    Hit flags + pnl should reflect the correct outcome end-to-end.
    """
    match = _finished_match(make_match, utc, home_score=2, away_score=1)
    pred = _insert_prediction(patched_session, match.id)
    _insert_value_signal(
        patched_session, match_id=match.id, prediction_id=pred.id,
        outcome="home", odds=1.85, signal_level=2,
    )

    result = settlement_tasks._settle_match(match.id)

    assert result == {"match_id": match.id, "settled": 1, "red_hits": 1}

    persisted = patched_session.query(PredictionResult).filter_by(prediction_id=pred.id).one()
    assert persisted.actual_home_score == 2
    assert persisted.actual_away_score == 1
    assert persisted.result_1x2_hit is True
    # Top scores include "2-1" → score market also hit.
    assert persisted.result_score_hit is True
    # 2+1 = 3 goals > 2.5 line with predicted "over" → OU hit.
    assert persisted.result_ou25_hit is True
    # Both teams scored → BTTS predicted yes → hit.
    assert persisted.result_btts_hit is True
    assert persisted.best_ev_outcome == "home"
    assert persisted.best_ev_hit is True
    # pnl on a winning unit bet = odds - 1.
    assert persisted.pnl_unit == pytest.approx(Decimal("0.85"), abs=Decimal("0.01"))


def test_settle_match_idempotent(patched_session, make_match, utc):
    """A second run on the same match must NOT insert duplicate result rows."""
    match = _finished_match(make_match, utc)
    pred = _insert_prediction(patched_session, match.id)

    first = settlement_tasks._settle_match(match.id)
    assert first["settled"] == 1

    second = settlement_tasks._settle_match(match.id)
    assert second["settled"] == 0, "re-run should be a no-op"

    rows = patched_session.query(PredictionResult).filter_by(prediction_id=pred.id).all()
    assert len(rows) == 1


def test_settle_match_skips_when_scores_missing(patched_session, make_match, utc):
    """A match flagged 'finished' before the data feed shipped the score is a no-op."""
    match = make_match(utc(2026, 5, 1, 18), home_score=None, away_score=None, status="finished")
    _insert_prediction(patched_session, match.id)

    result = settlement_tasks._settle_match(match.id)

    assert result == {"match_id": match.id, "settled": 0, "red_hits": 0}
    assert patched_session.query(PredictionResult).count() == 0


def test_settle_match_records_loss_correctly(patched_session, make_match, utc):
    """Predicted home, actual away win → 1x2 miss + best-ev miss with pnl = -1."""
    match = _finished_match(make_match, utc, home_score=0, away_score=2)
    pred = _insert_prediction(
        patched_session, match.id,
        prob_home=0.55, prob_draw=0.25, prob_away=0.20,
    )
    _insert_value_signal(
        patched_session, match_id=match.id, prediction_id=pred.id,
        outcome="home", odds=2.10, signal_level=2,
    )

    settlement_tasks._settle_match(match.id)

    row = patched_session.query(PredictionResult).filter_by(prediction_id=pred.id).one()
    assert row.result_1x2_hit is False
    assert row.best_ev_hit is False
    assert row.pnl_unit == pytest.approx(Decimal("-1.0"), abs=Decimal("0.01"))


def test_settle_match_handles_prediction_without_signal(patched_session, make_match, utc):
    """No odds-analysis rows → best_ev fields stay null + pnl = 0 (no bet placed)."""
    match = _finished_match(make_match, utc, home_score=1, away_score=1)
    pred = _insert_prediction(patched_session, match.id)
    # Deliberately skip OddsAnalysis insertion.

    settlement_tasks._settle_match(match.id)

    row = patched_session.query(PredictionResult).filter_by(prediction_id=pred.id).one()
    assert row.best_ev_outcome is None
    assert row.best_ev_odds is None
    assert row.best_ev_hit is None
    # No signal → no bet placed → pnl is 0, not -1.
    assert row.pnl_unit == pytest.approx(Decimal("0"), abs=Decimal("0.001"))


def test_settle_match_recomputes_track_record(patched_session, make_match, utc):
    """A successful settlement must refresh the cached track_record_stats matrix."""
    match = _finished_match(make_match, utc, home_score=2, away_score=1)
    _insert_prediction(patched_session, match.id)

    assert patched_session.query(TrackRecordStat).count() == 0

    settlement_tasks._settle_match(match.id)

    stats = patched_session.query(TrackRecordStat).all()
    # Recompute writes one row per (stat_type, period). 6 stat types × 4
    # periods = 24 cells.
    assert len(stats) == 24
    # All-time 1x2 hit-rate should reflect 1 hit / 1 total = 100%.
    all_time_1x2 = next(
        (s for s in stats if s.stat_type == "1x2" and s.period == "all_time"),
        None,
    )
    assert all_time_1x2 is not None
    assert all_time_1x2.total_predictions == 1
    assert all_time_1x2.hits == 1


# ---------------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------------


def test_scanner_dispatches_unsettled_only(
    patched_session, make_match, utc, monkeypatch, _silence_side_effects
):
    """_scan_and_dispatch fans out one settle_match task per unsettled finished match."""
    long_ago = datetime.now(timezone.utc) - timedelta(hours=24)
    unsettled = make_match(long_ago, home_score=2, away_score=1, status="finished")
    _insert_prediction(patched_session, unsettled.id)

    already_done = make_match(long_ago, home_score=1, away_score=0, status="finished")
    pred = _insert_prediction(patched_session, already_done.id)
    # Pre-seed a PredictionResult so the NOT-EXISTS subquery excludes this match.
    patched_session.add(PredictionResult(
        prediction_id=pred.id, match_id=already_done.id,
        actual_home_score=1, actual_away_score=0,
        result_1x2_hit=True, result_score_hit=False,
        settled_at=datetime.now(timezone.utc),
    ))
    patched_session.flush()

    out = settlement_tasks._scan_and_dispatch()

    assert out["dispatched"] == 1, "should only dispatch the unsettled match"
    # _silence_side_effects records every send_task — confirm the unsettled match's id was used.
    dispatched_names = [name for name, _args in _silence_side_effects]
    dispatched_args = [args for _name, args in _silence_side_effects]
    assert "settlement.settle_match" in dispatched_names
    assert [unsettled.id] in dispatched_args


def test_scanner_respects_cutoff_delay(patched_session, make_match, utc, _silence_side_effects):
    """A match finishing only a few minutes ago is too fresh to settle — skip it."""
    just_now = datetime.now(timezone.utc) - timedelta(minutes=5)
    fresh = make_match(just_now, home_score=2, away_score=1, status="finished")
    _insert_prediction(patched_session, fresh.id)

    out = settlement_tasks._scan_and_dispatch()

    assert out["dispatched"] == 0, "match finished < MATCH_SETTLE_DELAY_HOURS ago is too fresh"

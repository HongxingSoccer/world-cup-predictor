"""Celery tasks for post-match settlement.

Two-task pattern (recommended in the spec):

    1. `scan_finished_matches` runs hourly via Beat. It looks at finished
       matches that closed at least `MATCH_SETTLE_DELAY_HOURS` ago and have
       at least one un-settled prediction, then enqueues a per-match
       settlement task. The delay gives upstream feeds time to publish the
       canonical scoreline.

    2. `settle_match_prediction(match_id)` does the actual work — for every
       prediction on the match, runs the deterministic checks in
       `src.utils.settlement`, writes a `prediction_results` row, recomputes
       the cached `track_record_stats`, emits a Kafka `prediction.red_hit`
       event when the 1x2 was correct, and clears Redis caches.

Idempotency: the `prediction_results` UNIQUE on `prediction_id` means a
re-run is a no-op for already-settled predictions. The scanner therefore
filters them out cheaply with a NOT-EXISTS subquery.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import structlog
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from src.config.celery_config import (
    DEFAULT_MAX_RETRIES,
    DEFAULT_RETRY_BACKOFF,
    DEFAULT_RETRY_BACKOFF_MAX,
    app,
)
from src.events.producer import build_producer
from src.events.schemas import PredictionRedHitPayload
from src.events.topics import TOPIC_PREDICTION_RED_HIT
from src.models.match import Match
from src.models.odds_analysis import OddsAnalysis
from src.models.prediction import Prediction
from src.models.prediction_result import PredictionResult
from src.models.team import Team
from src.utils.db import session_scope
from src.utils.settlement import (
    SettlementVerdict,
    actual_result_letter,
    evaluate_best_ev,
    is_1x2_hit,
    is_btts_hit,
    is_ou25_hit,
    is_score_hit,
)
from src.utils.track_record import recompute_all

logger = structlog.get_logger(__name__)

# How long after kickoff we wait before trying to settle a match. Two hours
# is the project standard — gives the data feeds time to ship a canonical
# scoreline + finalised stats.
MATCH_SETTLE_DELAY_HOURS: int = 2

# Cap how many matches the scanner enqueues per tick so a backlog of
# un-settled finishes can't drown the queue.
SCAN_BATCH_SIZE: int = 100

# Redis cache keys to invalidate when track-record state changes. Mirrors
# what `MatchService.predictions_today` writes from the FastAPI side.
_CACHE_KEYS_TO_CLEAR: tuple[str, ...] = (
    "wcp:track:*",
    "wcp:predictions:today:*",
)


# --- Beat task: hourly scanner -------------------------------------------


@app.task(
    bind=True,
    name="settlement.scan_finished_matches",
    max_retries=DEFAULT_MAX_RETRIES,
    retry_backoff=DEFAULT_RETRY_BACKOFF,
    retry_backoff_max=DEFAULT_RETRY_BACKOFF_MAX,
)
def scan_finished_matches(self) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    """Find finished-but-unsettled matches and fan out per-match settlement."""
    try:
        return _scan_and_dispatch()
    except Exception as exc:
        logger.exception("settlement_scan_failed")
        raise self.retry(exc=exc) from exc


def _scan_and_dispatch() -> dict[str, Any]:
    """Returns {scanned: int, dispatched: int} for Flower / audit logs."""
    cutoff = datetime.now(UTC) - timedelta(hours=MATCH_SETTLE_DELAY_HOURS)
    dispatched = 0
    with session_scope() as session:
        candidates = list(
            session.execute(
                select(Match.id)
                .where(
                    Match.status == "finished",
                    Match.match_date <= cutoff,
                    Match.home_score.is_not(None),
                    Match.away_score.is_not(None),
                    # Has at least one prediction we haven't settled yet.
                    select(Prediction.id)
                    .where(Prediction.match_id == Match.id)
                    .where(
                        ~select(PredictionResult.id)
                        .where(PredictionResult.prediction_id == Prediction.id)
                        .exists()
                    )
                    .exists(),
                )
                .order_by(Match.match_date)
                .limit(SCAN_BATCH_SIZE)
            ).scalars()
        )

    for match_id in candidates:
        app.send_task("settlement.settle_match", args=[int(match_id)])
        dispatched += 1
    logger.info("settlement_scan_dispatched", scanned=len(candidates), dispatched=dispatched)
    return {"scanned": len(candidates), "dispatched": dispatched}


# --- Per-match settlement -------------------------------------------------


@app.task(
    bind=True,
    name="settlement.settle_match",
    max_retries=DEFAULT_MAX_RETRIES,
    retry_backoff=DEFAULT_RETRY_BACKOFF,
    retry_backoff_max=DEFAULT_RETRY_BACKOFF_MAX,
)
def settle_match_prediction(self, match_id: int) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    """Settle every un-settled prediction for `match_id`."""
    try:
        return _settle_match(int(match_id))
    except Exception as exc:
        logger.exception("settle_match_failed", match_id=match_id)
        raise self.retry(exc=exc) from exc


def _settle_match(match_id: int) -> dict[str, Any]:
    producer = build_producer()
    settled = 0
    red_hits = 0
    try:
        with session_scope() as session:
            match = session.get(Match, match_id)
            if match is None or match.home_score is None or match.away_score is None:
                logger.warning("settle_match_missing_data", match_id=match_id)
                return {"match_id": match_id, "settled": 0, "red_hits": 0}

            home_score = int(match.home_score)
            away_score = int(match.away_score)
            home_team = session.get(Team, match.home_team_id)
            away_team = session.get(Team, match.away_team_id)

            predictions = list(
                session.execute(
                    select(Prediction).where(Prediction.match_id == match_id)
                ).scalars()
            )

            new_red_hit_ids: list[int] = []
            for prediction in predictions:
                if _already_settled(session, prediction.id):
                    continue
                verdict = _evaluate_prediction(session, prediction, home_score, away_score)
                result_row = _persist_result(
                    session, prediction, match_id, home_score, away_score, verdict
                )
                settled += 1
                if verdict.result_1x2_hit:
                    red_hits += 1
                    new_red_hit_ids.append(result_row.id)
                    _emit_red_hit_event(
                        producer=producer,
                        prediction=prediction,
                        home_team=home_team.name if home_team else "?",
                        away_team=away_team.name if away_team else "?",
                        home_score=home_score,
                        away_score=away_score,
                        pnl_unit=verdict.pnl_unit,
                    )

            if settled:
                # Recompute the entire track-record matrix; cheap relative to
                # the per-match settlement above, and keeps the public
                # scoreboard exactly in sync with the underlying data.
                recompute_all(session)
                _invalidate_caches()
        # Fan out red-hit card renders AFTER the settlement transaction
        # commits so the per-platform tasks see the persisted results row.
        for result_id in new_red_hit_ids:
            try:
                app.send_task("card.fanout_red_hit", args=[int(result_id)])
            except Exception as exc:
                logger.warning("red_hit_card_dispatch_failed", error=str(exc))
    finally:
        producer.close()

    # M9.5 — settle any user positions for this match. Best-effort: if
    # the position settlement fails for any reason, log + continue (the
    # prediction settlement above is the load-bearing path; positions
    # are user-tracked and can be reconciled later if needed).
    try:
        settle_positions_for_match(match_id)
    except Exception as exc:
        logger.warning("position_settlement_failed", match_id=match_id, error=str(exc))

    logger.info(
        "settle_match_completed",
        match_id=match_id,
        settled=settled,
        red_hits=red_hits,
    )
    return {"match_id": match_id, "settled": settled, "red_hits": red_hits}


def settle_positions_for_match(match_id: int) -> dict[str, int]:
    """Compute P/L for every active/hedged position on ``match_id``.

    Called by :func:`settle_match_prediction` once the match's prediction
    settlement transaction commits. Independent transaction so a position
    failure can't corrupt the prediction settlement row.

    Returns a small counts dict for diagnostics.
    """
    # Local imports — settlement-tasks isn't the position-service's
    # owner, so keep coupling at the boundary.
    from src.models.user_position import UserPosition
    from src.push.dispatcher import NotificationDispatcher

    settled_count = 0
    with session_scope() as session:
        match = session.get(Match, match_id)
        if match is None or match.home_score is None or match.away_score is None:
            return {"match_id": match_id, "settled": 0}

        home, away = match.home_score, match.away_score
        # Outcome (1x2) derivation.
        if home > away:
            outcome_1x2 = "home"
        elif home < away:
            outcome_1x2 = "away"
        else:
            outcome_1x2 = "draw"
        total = home + away
        # Over/under bin commonly used for OU 2.5; positions store the
        # outcome as 'over' or 'under' but the *line* isn't recorded on
        # user_positions today. We assume the standard 2.5 line.
        outcome_ou = "over" if total > 2.5 else "under"
        outcome_btts = "yes" if home > 0 and away > 0 else "no"

        positions = session.execute(
            select(UserPosition).where(
                UserPosition.match_id == match_id,
                UserPosition.status.in_(["active", "hedged"]),
            )
        ).scalars().all()

        for position in positions:
            won = _position_outcome_match(
                position.market,
                position.outcome,
                outcome_1x2,
                outcome_ou,
                outcome_btts,
            )
            pnl = (
                position.stake * (position.odds - Decimal("1"))
                if won
                else -position.stake
            )
            position.settlement_pnl = pnl.quantize(Decimal("0.01"))
            position.status = "settled"
            position.updated_at = datetime.now(UTC)
            settled_count += 1

            try:
                NotificationDispatcher.send_position_settled(session, position)
            except Exception as exc:
                logger.warning(
                    "position_settled_notify_failed",
                    position_id=position.id,
                    error=str(exc),
                )

        session.commit()

    return {"match_id": match_id, "settled": settled_count}


def _position_outcome_match(
    market: str,
    outcome: str,
    outcome_1x2: str,
    outcome_ou: str,
    outcome_btts: str,
) -> bool:
    """Whether the user's position landed on the right side."""
    if market in ("1x2", "asian_handicap"):
        return outcome == outcome_1x2
    if market == "over_under":
        return outcome == outcome_ou
    if market == "btts":
        return outcome == outcome_btts
    return False


# --- Internal helpers ------------------------------------------------------


def _already_settled(session: Session, prediction_id: int) -> bool:
    return session.execute(
        select(PredictionResult.id).where(
            PredictionResult.prediction_id == prediction_id
        )
    ).first() is not None


def _evaluate_prediction(
    session: Session,
    prediction: Prediction,
    home_score: int,
    away_score: int,
) -> SettlementVerdict:
    """Run all six settlement checks for one prediction."""
    result_1x2 = is_1x2_hit(
        prob_home=float(prediction.prob_home_win),
        prob_draw=float(prediction.prob_draw),
        prob_away=float(prediction.prob_away_win),
        home_score=home_score,
        away_score=away_score,
    )
    result_score = is_score_hit(
        prediction.top_scores or [], home_score=home_score, away_score=away_score
    )
    result_ou25 = is_ou25_hit(
        prediction.over_under_probs or {},
        home_score=home_score,
        away_score=away_score,
    )
    result_btts = is_btts_hit(
        prediction.btts_prob, home_score=home_score, away_score=away_score
    )

    best_ev_row = _best_ev_row(session, prediction.id)
    if best_ev_row is None:
        best_ev_outcome: str | None = None
        best_ev_odds: Decimal | None = None
        best_ev_market: str | None = None
        signal_level: int | None = None
    else:
        best_ev_outcome = best_ev_row.outcome
        best_ev_odds = best_ev_row.best_odds
        best_ev_market = best_ev_row.market_type
        signal_level = best_ev_row.signal_level

    best_ev_hit, pnl_unit = evaluate_best_ev(
        market_type=best_ev_market,
        outcome=best_ev_outcome,
        odds=best_ev_odds,
        signal_level=signal_level,
        home_score=home_score,
        away_score=away_score,
    )

    return SettlementVerdict(
        result_1x2_hit=result_1x2,
        result_score_hit=result_score,
        result_ou25_hit=result_ou25,
        result_btts_hit=result_btts,
        best_ev_outcome=best_ev_outcome,
        best_ev_odds=best_ev_odds,
        best_ev_hit=best_ev_hit,
        pnl_unit=pnl_unit,
    )


def _best_ev_row(session: Session, prediction_id: int) -> OddsAnalysis | None:
    """Highest signal-level analysis row for a prediction; ties broken by EV."""
    return session.execute(
        select(OddsAnalysis)
        .where(OddsAnalysis.prediction_id == prediction_id)
        .order_by(desc(OddsAnalysis.signal_level), desc(OddsAnalysis.ev))
        .limit(1)
    ).scalar_one_or_none()


def _persist_result(
    session: Session,
    prediction: Prediction,
    match_id: int,
    home_score: int,
    away_score: int,
    verdict: SettlementVerdict,
) -> PredictionResult:
    """Insert the row + flush so the auto-increment id is available for FK use."""
    row = PredictionResult(
        prediction_id=prediction.id,
        match_id=match_id,
        actual_home_score=home_score,
        actual_away_score=away_score,
        result_1x2_hit=verdict.result_1x2_hit,
        result_score_hit=verdict.result_score_hit,
        result_ou25_hit=verdict.result_ou25_hit,
        result_btts_hit=verdict.result_btts_hit,
        best_ev_outcome=verdict.best_ev_outcome,
        best_ev_odds=verdict.best_ev_odds,
        best_ev_hit=verdict.best_ev_hit,
        pnl_unit=verdict.pnl_unit,
    )
    session.add(row)
    session.flush()
    return row


def _emit_red_hit_event(
    *,
    producer,  # type: ignore[no-untyped-def]
    prediction: Prediction,
    home_team: str,
    away_team: str,
    home_score: int,
    away_score: int,
    pnl_unit: Decimal,
) -> None:
    payload = PredictionRedHitPayload(
        prediction_id=prediction.id,
        match_id=prediction.match_id,
        home_team=home_team,
        away_team=away_team,
        home_score=home_score,
        away_score=away_score,
        confidence_score=int(prediction.confidence_score),
        confidence_level=prediction.confidence_level,  # type: ignore[arg-type]
        pnl_unit=float(pnl_unit),
        settled_at=datetime.now(UTC),
    )
    try:
        producer.publish(
            event_type=TOPIC_PREDICTION_RED_HIT,
            key=str(prediction.match_id),
            payload=payload,
        )
    except Exception as exc:
        # Kafka hiccup must not roll back the DB write — log and move on.
        logger.warning("red_hit_event_publish_failed", error=str(exc))


def _invalidate_caches() -> None:
    """Best-effort Redis invalidation for the track-record / today caches."""
    try:
        import redis

        from src.config.settings import settings

        client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
        for pattern in _CACHE_KEYS_TO_CLEAR:
            keys = list(client.scan_iter(match=pattern, count=200))
            if keys:
                client.delete(*keys)
    except Exception as exc:
        logger.debug("cache_invalidation_skipped", error=str(exc))


# Convenience re-export so consumers see the canonical settled-result letter
# without re-importing from utils.settlement.
__all__ = [
    "MATCH_SETTLE_DELAY_HOURS",
    "actual_result_letter",
    "scan_finished_matches",
    "settle_match_prediction",
]

"""Batch-generate predictions for upcoming matches.

Fills the ``predictions`` table so the Java API's ``/api/v1/matches/today``
and the FastAPI ``/api/v1/predictions/today`` endpoints have content. Loads
the same MLflow-served Poisson model the FastAPI app uses, then iterates
upcoming `scheduled` matches in the configured date window.

Idempotent: matches that already have a prediction with the current
``model_version`` + ``feature_version`` are skipped. Pass ``--force`` after
re-training to refresh existing rows in place — the script bypasses the
``predictions_immutable`` trigger for the affected matches only, and busts
the Redis ``/predictions/today`` cache so the new probabilities surface
immediately.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from typing import Iterable

import structlog
from sqlalchemy import delete, select, text

from src.config.settings import settings
from src.ml.features.pipeline import FeaturePipeline
from src.ml.models.confidence import ConfidenceCalculator
from src.ml.models.poisson import PoissonBaselineModel
from src.ml.odds.analyzer import OddsAnalyzer
from src.ml.prediction_service import PredictionService
from src.models.match import Match
from src.models.odds_analysis import OddsAnalysis
from src.models.prediction import Prediction
from src.utils.db import session_scope
from src.utils.logging import configure_logging

logger = structlog.get_logger(__name__)

_TODAY_CACHE_PREFIX: str = "wcp:predictions:today:*"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--days-ahead",
        type=int,
        default=60,
        help="Generate predictions for matches kicking off within the next N days (default 60).",
    )
    p.add_argument(
        "--days-back",
        type=int,
        default=0,
        help="Also include matches that kicked off within the past N days (default 0).",
    )
    p.add_argument(
        "--model-path",
        default=None,
        help="Optional path to a pickled trained PoissonBaselineModel. "
        "If omitted, an untrained model is used (uniform prior).",
    )
    p.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Hard cap on the number of matches to process this run.",
    )
    p.add_argument(
        "--force",
        action="store_true",
        help="Drop existing predictions (and their odds_analysis dependents) "
        "for the same model_version before re-predicting. Use this after "
        "re-training the model on a wider dataset; without it the existing "
        "rows would be skipped because of the (match_id, model_version) "
        "uniqueness constraint.",
    )
    return p.parse_args()


def main(args: argparse.Namespace) -> int:
    model = _load_model(args.model_path)
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(days=args.days_back)
    window_end = now + timedelta(days=args.days_ahead)

    totals = {"considered": 0, "predicted": 0, "skipped": 0, "errors": 0}

    with session_scope() as session:
        match_ids = _select_match_ids(session, window_start, window_end, args.limit)
        totals["considered"] = len(match_ids)
        logger.info("predict_batch_started", count=len(match_ids), force=args.force)

    if args.force and match_ids:
        deleted = _drop_existing_predictions(model.get_model_version(), match_ids)
        _bust_today_cache()
        totals["force_deleted"] = deleted

    for match_id in match_ids:
        try:
            with session_scope() as session:
                if not args.force and _already_predicted(
                    session, match_id, model.get_model_version()
                ):
                    totals["skipped"] += 1
                    continue
                service = PredictionService(
                    db_session=session,
                    model=model,
                    feature_pipeline=FeaturePipeline(session),
                    odds_analyzer=OddsAnalyzer(session),
                    confidence_calculator=ConfidenceCalculator(),
                )
                service.generate_prediction(match_id, publish=True)
                totals["predicted"] += 1
        except Exception as exc:  # noqa: BLE001 — keep the batch going
            logger.warning("predict_failed", match_id=match_id, error=repr(exc))
            totals["errors"] += 1

    logger.info("predict_batch_done", **totals)
    return 0


def _select_match_ids(
    session, window_start: datetime, window_end: datetime, limit: int | None
) -> list[int]:
    stmt = (
        select(Match.id)
        .where(
            Match.match_date >= window_start,
            Match.match_date < window_end,
            Match.status.in_(("scheduled", "live")),
        )
        .order_by(Match.match_date)
    )
    if limit:
        stmt = stmt.limit(limit)
    return [row[0] for row in session.execute(stmt).all()]


def _already_predicted(session, match_id: int, model_version: str) -> bool:
    return (
        session.execute(
            select(Prediction.id)
            .where(
                Prediction.match_id == match_id,
                Prediction.model_version == model_version,
            )
            .limit(1)
        ).scalar()
        is not None
    )


def _drop_existing_predictions(model_version: str, match_ids: list[int]) -> int:
    """Delete predictions (and their odds_analysis FK dependents) for ``match_ids``
    at ``model_version``, bypassing the ``predictions_immutable`` trigger only
    for the duration of the DELETE.

    The trigger is the DB-level enforcement of "predictions are append-only";
    the script-level toggle is a deliberate development override scoped to
    ``--force`` runs.
    """
    pred_id_subq = select(Prediction.id).where(
        Prediction.match_id.in_(match_ids),
        Prediction.model_version == model_version,
    )
    with session_scope() as session:
        oa_deleted = session.execute(
            delete(OddsAnalysis).where(OddsAnalysis.prediction_id.in_(pred_id_subq))
        ).rowcount
        session.execute(text("ALTER TABLE predictions DISABLE TRIGGER predictions_immutable"))
        try:
            pred_deleted = session.execute(
                delete(Prediction).where(
                    Prediction.match_id.in_(match_ids),
                    Prediction.model_version == model_version,
                )
            ).rowcount
        finally:
            session.execute(text("ALTER TABLE predictions ENABLE TRIGGER predictions_immutable"))
    logger.info(
        "force_dropped_existing_predictions",
        model_version=model_version,
        predictions_deleted=int(pred_deleted or 0),
        odds_analysis_deleted=int(oa_deleted or 0),
    )
    return int(pred_deleted or 0)


def _bust_today_cache() -> None:
    """Drop every ``wcp:predictions:today:*`` Redis key so the next request
    re-reads from Postgres. No-op if Redis is unreachable."""
    try:
        import redis

        client = redis.Redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=2.0,
            socket_timeout=5.0,
        )
        keys = list(client.scan_iter(match=_TODAY_CACHE_PREFIX, count=200))
        if keys:
            client.delete(*keys)
        logger.info("today_cache_busted", keys_deleted=len(keys))
    except Exception as exc:  # noqa: BLE001 — redis being down isn't fatal
        logger.warning("today_cache_bust_failed", error=str(exc))


def _load_model(model_path: str | None):  # type: ignore[no-untyped-def]
    """Resolve which trained model to use, in order of preference:

    1. Explicit ``--model-path`` (joblib pickle).
    2. The MLflow Production-staged version of ``settings.ACTIVE_MODEL_NAME``.
       This is the same loader the FastAPI app uses at startup, so the
       force-refresh path stays in sync with what the API will serve.
    3. Inline training of the Poisson baseline as a last-resort fallback.
    """
    if model_path is not None:
        import joblib

        model = joblib.load(model_path)
        logger.info(
            "predict_model_loaded_from_path",
            path=model_path,
            version=model.get_model_version(),
        )
        return model

    # Try the same MLflow loader the API uses.
    try:
        from src.ml.training.mlflow_utils import load_production_model

        loaded = load_production_model(settings.ACTIVE_MODEL_NAME)
        if loaded is not None:
            logger.info(
                "predict_model_loaded_from_mlflow",
                version=loaded.get_model_version(),
                trained_on_n_matches=loaded.params.get("trained_on_n_matches"),
            )
            return loaded
    except Exception as exc:  # mlflow unreachable, missing model, etc.
        logger.warning("predict_model_mlflow_load_failed", error=str(exc))

    return _train_inline_model()


def _train_inline_model() -> PoissonBaselineModel:
    """Fallback: train the Poisson baseline directly from ``match_features``.

    Used when MLflow is unreachable AND no explicit ``--model-path`` was
    supplied. Hardcoded to ``PoissonBaselineModel`` because the only point
    of this fallback is to avoid a hard failure — if the operator wants a
    specific model class they should register it in MLflow.
    """
    import pandas as pd
    from sqlalchemy import select

    from src.models.match import Match
    from src.models.match_feature import MatchFeature

    rows: list[dict] = []
    with session_scope() as session:
        stmt = (
            select(
                MatchFeature.match_id,
                MatchFeature.features,
                MatchFeature.label_home_score,
                MatchFeature.label_away_score,
                Match.match_date,
            )
            .join(Match, Match.id == MatchFeature.match_id)
            .where(MatchFeature.feature_version == "v1")
        )
        for row in session.execute(stmt).all():
            record = {
                "match_id": row.match_id,
                "match_date": row.match_date,
                "label_home_score": row.label_home_score,
                "label_away_score": row.label_away_score,
            }
            record.update(row.features or {})
            rows.append(record)
    if not rows:
        raise RuntimeError("no rows in match_features (run scripts.compute_features first)")
    df = pd.DataFrame.from_records(rows)
    model = PoissonBaselineModel()
    model.train(df)
    logger.info(
        "predict_model_trained_inline",
        rows=len(df),
        version=model.get_model_version(),
        league_avg_goals=float(model.params.get("league_avg_goals", 0.0)),
        home_factor=float(model.params.get("home_factor", 0.0)),
    )
    return model


def _iter_chunks(values: Iterable[int], size: int) -> Iterable[list[int]]:
    chunk: list[int] = []
    for v in values:
        chunk.append(v)
        if len(chunk) == size:
            yield chunk
            chunk = []
    if chunk:
        yield chunk


if __name__ == "__main__":
    configure_logging(json_logs=False)
    try:
        sys.exit(main(parse_args()))
    except KeyboardInterrupt:
        logger.warning("predict_interrupted")
        sys.exit(130)

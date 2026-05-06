"""Celery tasks for rolling per-match prediction generation.

Companion to ``match.dispatch_dynamic_jobs`` in :mod:`src.tasks.match_tasks`.
The dispatcher selects scheduled matches in the [+3d, +5d] window that have
no prediction yet, fans them out to ``predictions.generate_pre_kickoff``,
and this module owns the actual generation work.

The model is loaded once per worker process and cached at module level —
each task call would otherwise hit MLflow on the registry, multiplying
network round-trips by the number of upcoming matches.
"""
from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy import select

from src.config.celery_config import (
    DEFAULT_MAX_RETRIES,
    DEFAULT_RETRY_BACKOFF,
    DEFAULT_RETRY_BACKOFF_MAX,
    app,
)
from src.ml.features.pipeline import FeaturePipeline
from src.ml.models.confidence import ConfidenceCalculator
from src.ml.models.poisson import PoissonBaselineModel
from src.ml.odds.analyzer import OddsAnalyzer
from src.ml.prediction_service import PredictionService
from src.models.prediction import Prediction
from src.utils.db import session_scope

logger = structlog.get_logger(__name__)

# Process-local cache. Workers run as separate processes, so each gets its
# own copy after the first call — fine for this footprint (a few hundred
# floats).
_cached_model: PoissonBaselineModel | None = None


@app.task(
    bind=True,
    name="predictions.generate_pre_kickoff",
    max_retries=DEFAULT_MAX_RETRIES,
    retry_backoff=DEFAULT_RETRY_BACKOFF,
    retry_backoff_max=DEFAULT_RETRY_BACKOFF_MAX,
)
def generate_pre_kickoff_prediction(self, match_id: int) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    """Persist a prediction for ``match_id`` if one doesn't already exist.

    The ``(match_id, model_version)`` UNIQUE constraint plus the
    ``predictions_immutable`` trigger make this a no-op if a prediction
    already exists at the current version — the task short-circuits before
    calling the model. Refresh after re-training is the operator's job
    (``scripts.generate_predictions --force``); the rolling dispatcher is
    fire-and-forget.
    """
    try:
        model = _get_prediction_model()
        if not model.params:
            logger.warning(
                "predictions_pre_kickoff_skipped_untrained_model", match_id=match_id
            )
            return {"match_id": match_id, "skipped": "untrained_model"}

        with session_scope() as session:
            existing = session.execute(
                select(Prediction.id)
                .where(
                    Prediction.match_id == match_id,
                    Prediction.model_version == model.get_model_version(),
                )
                .limit(1)
            ).scalar()
            if existing is not None:
                return {"match_id": match_id, "skipped": "already_predicted"}

            service = PredictionService(
                db_session=session,
                model=model,
                feature_pipeline=FeaturePipeline(session),
                odds_analyzer=OddsAnalyzer(session),
                confidence_calculator=ConfidenceCalculator(),
            )
            result = service.generate_prediction(match_id, publish=True)
            return {
                "match_id": match_id,
                "predicted": True,
                "prediction_id": result.prediction_id,
                "confidence": result.confidence_score,
            }
    except Exception as exc:
        logger.exception(
            "predictions_generate_pre_kickoff_failed", match_id=match_id
        )
        raise self.retry(exc=exc) from exc


def _get_prediction_model() -> PoissonBaselineModel:
    """Lazy-load + cache the production model.

    Tries MLflow's registry first (same path the API uses at startup); falls
    back to in-process training off ``match_features`` if the registry is
    unreachable, so the worker is functional even without a Production-staged
    version. Tests can reset the cache by setting ``_cached_model`` to None.
    """
    global _cached_model
    if _cached_model is not None:
        return _cached_model
    _cached_model = _try_load_from_mlflow() or _train_inline()
    logger.info(
        "prediction_task_model_ready",
        version=_cached_model.get_model_version(),
        trained=bool(_cached_model.params),
    )
    return _cached_model


def _try_load_from_mlflow() -> PoissonBaselineModel | None:
    try:
        from src.ml.training.mlflow_utils import load_production_model

        loaded = load_production_model("poisson_v1")
    except Exception as exc:  # mlflow unreachable, registry empty, etc.
        logger.warning("prediction_task_mlflow_unreachable", error=str(exc))
        return None
    if loaded is None:
        return None
    if isinstance(loaded, PoissonBaselineModel):
        return loaded
    # The MLflow loader is typed BasePredictionModel; we only support Poisson here.
    return None


@app.task(
    bind=True,
    name="tournament.simulate_daily",
    max_retries=DEFAULT_MAX_RETRIES,
    retry_backoff=DEFAULT_RETRY_BACKOFF,
    retry_backoff_max=DEFAULT_RETRY_BACKOFF_MAX,
)
def tournament_simulate_daily(self) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    """Run the Monte Carlo tournament simulator and persist a fresh result.

    The driver lives in :mod:`scripts.run_tournament_simulation` and exposes
    :func:`run_and_persist` for in-process callers. We intentionally pin the
    seed to ``None`` here so each daily run uses fresh randomness — the goal
    is to reflect the latest persisted predictions, not to be reproducible.
    """
    try:
        # Local import keeps script-level imports (pandas, etc.) out of the
        # task module's hot-import path.
        from scripts.run_tournament_simulation import (  # noqa: PLC0415
            DEFAULT_TRIALS,
            run_and_persist,
        )

        outcome = run_and_persist(trials=DEFAULT_TRIALS, seed=None)
        if outcome is None:
            logger.warning("tournament_simulate_daily_no_data")
            return {"status": "skipped", "reason": "no_predictions_to_simulate"}
        sim_id, payload = outcome
        leaderboard = payload.get("leaderboard") or []
        return {
            "status": "ok",
            "simulation_id": sim_id,
            "trials": DEFAULT_TRIALS,
            "teams": len(leaderboard),
        }
    except Exception as exc:
        logger.exception("tournament_simulate_daily_failed")
        raise self.retry(exc=exc) from exc


def _train_inline() -> PoissonBaselineModel:
    """Fit a Poisson baseline directly from the persisted feature table.

    Mirrors the trainer in :mod:`scripts.train_model` but skips MLflow and
    parquet — the worker just wants something it can serve until a
    Production version is registered.
    """
    import pandas as pd

    from src.models.match import Match
    from src.models.match_feature import MatchFeature

    rows: list[dict[str, Any]] = []
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
            record: dict[str, Any] = {
                "match_id": row.match_id,
                "match_date": row.match_date,
                "label_home_score": row.label_home_score,
                "label_away_score": row.label_away_score,
            }
            record.update(row.features or {})
            rows.append(record)

    model = PoissonBaselineModel()
    if not rows:
        logger.warning("prediction_task_inline_train_no_features")
        return model  # untrained — caller short-circuits via .params check

    df = pd.DataFrame.from_records(rows)
    model.train(df)
    return model

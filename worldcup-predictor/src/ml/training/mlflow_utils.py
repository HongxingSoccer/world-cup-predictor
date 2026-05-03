"""MLflow tracking + registry helpers.

Phase-2 uses MLflow for three things:

    1. Recording each training run (`log_training_run`).
    2. Recording backtest runs and attaching the HTML report
       (`log_backtest_run`).
    3. Registering trained models and pulling a "Production"-staged version
       at API startup (`register_model` + `load_production_model`).

We deliberately avoid `mlflow.pyfunc` / `mlflow.sklearn` flavours — our
models are tiny and serialise via the `BasePredictionModel.save/load`
interface, which round-trips reliably without an mlflow-flavour wrapper.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

import structlog

from src.config.settings import settings
from src.ml.models.base import BasePredictionModel
from src.ml.models.poisson import PoissonBaselineModel

logger = structlog.get_logger(__name__)

# Pre-registered Phase-2 + reserved Phase-3/4 experiments. The training and
# backtest scripts default to `wcp-poisson-baseline` / `wcp-backtest`.
PHASE2_EXPERIMENTS: tuple[str, ...] = (
    "wcp-poisson-baseline",
    "wcp-feature-engineering",
    "wcp-backtest",
    "wcp-dixon-coles",
    "wcp-xgboost",
)

_MODEL_ARTIFACT_PATH: str = "model"
_MODEL_FILE_NAME: str = "model.json"


def init_mlflow(experiment_name: str | None = None) -> None:
    """Configure tracking URI + select (or create) an experiment.

    Safe to call multiple times — MLflow is idempotent on URI / experiment.
    Errors are logged but never raised so a missing tracking server doesn't
    abort the calling script.
    """
    import mlflow

    mlflow.set_tracking_uri(settings.MLFLOW_TRACKING_URI)
    target = experiment_name or settings.MLFLOW_DEFAULT_EXPERIMENT
    try:
        mlflow.set_experiment(target)
    except Exception as exc:  # mlflow.MlflowException + transport errors
        logger.warning("mlflow_set_experiment_failed", experiment=target, error=str(exc))


def log_training_run(
    model: BasePredictionModel,
    *,
    run_name: str,
    params: dict[str, Any],
    metrics: dict[str, float],
    artifacts: dict[str, Path] | None = None,
    tags: dict[str, str] | None = None,
) -> str | None:
    """Open an MLflow run, log everything, save the model artifact, return run_id.

    Returns:
        The MLflow run id on success, or `None` if MLflow was unreachable.
    """
    import mlflow

    try:
        with mlflow.start_run(run_name=run_name, tags=tags) as run:
            mlflow.log_params(params)
            mlflow.log_metrics({k: float(v) for k, v in metrics.items()})

            with tempfile.TemporaryDirectory() as tmp:
                target = Path(tmp) / _MODEL_FILE_NAME
                model.save(target)
                mlflow.log_artifact(str(target), artifact_path=_MODEL_ARTIFACT_PATH)

            for name, path in (artifacts or {}).items():
                if Path(path).exists():
                    mlflow.log_artifact(str(path), artifact_path=name)
            run_id = run.info.run_id
        logger.info("mlflow_training_logged", run_id=run_id, run_name=run_name)
        return run_id
    except Exception as exc:
        logger.error("mlflow_training_log_failed", error=str(exc))
        return None


def log_backtest_run(
    *,
    run_name: str,
    params: dict[str, Any],
    metrics: dict[str, float],
    report_path: Path | None = None,
    extras: dict[str, Path] | None = None,
) -> str | None:
    """Backtest twin of `log_training_run` — no model artifact, but logs the report."""
    import mlflow

    try:
        with mlflow.start_run(run_name=run_name) as run:
            mlflow.log_params(params)
            mlflow.log_metrics({k: float(v) for k, v in metrics.items()})
            if report_path is not None and report_path.exists():
                mlflow.log_artifact(str(report_path), artifact_path="report")
            for name, path in (extras or {}).items():
                if Path(path).exists():
                    mlflow.log_artifact(str(path), artifact_path=name)
            run_id = run.info.run_id
        logger.info("mlflow_backtest_logged", run_id=run_id, run_name=run_name)
        return run_id
    except Exception as exc:
        logger.error("mlflow_backtest_log_failed", error=str(exc))
        return None


def register_model(
    model_name: str,
    run_id: str,
    *,
    stage: str = "Staging",
) -> int | None:
    """Register the artifact as a new model version and transition it to `stage`."""
    import mlflow

    try:
        client = mlflow.tracking.MlflowClient()
        source = f"runs:/{run_id}/{_MODEL_ARTIFACT_PATH}"
        version = mlflow.register_model(model_uri=source, name=model_name)
        client.transition_model_version_stage(
            name=model_name,
            version=version.version,
            stage=stage,
            archive_existing_versions=False,
        )
        logger.info(
            "mlflow_model_registered",
            model_name=model_name,
            version=version.version,
            stage=stage,
        )
        return int(version.version)
    except Exception as exc:
        logger.error("mlflow_register_failed", error=str(exc))
        return None


def load_production_model(model_name: str) -> BasePredictionModel | None:
    """Pull the Production-staged model artifact and reload it into a `PoissonBaselineModel`.

    Returns `None` when the registry is unreachable or no Production version
    exists yet — callers fall back to an untrained default.
    """
    import mlflow

    init_mlflow()
    try:
        client = mlflow.tracking.MlflowClient()
        versions = client.get_latest_versions(model_name, stages=["Production"])
        if not versions:
            logger.info("mlflow_no_production_version", model_name=model_name)
            return None
        version = versions[0]
        download_dir = Path(
            mlflow.artifacts.download_artifacts(
                run_id=version.run_id, artifact_path=_MODEL_ARTIFACT_PATH
            )
        )
        model_file = download_dir / _MODEL_FILE_NAME
        model = PoissonBaselineModel()
        model.load(model_file)
        logger.info(
            "mlflow_production_model_loaded",
            model_name=model_name,
            version=version.version,
        )
        return model
    except Exception as exc:
        logger.warning("mlflow_load_production_failed", error=str(exc))
        return None


def write_run_id_to_file(path: Path | str, run_id: str | None) -> None:
    """Helper for shell scripts: dump the run id (or 'none') to disk."""
    Path(path).write_text(json.dumps({"run_id": run_id or ""}))
    if "MLFLOW_LAST_RUN_ID" not in os.environ and run_id:
        os.environ["MLFLOW_LAST_RUN_ID"] = run_id

"""Train a Poisson baseline (or other model) and log the run to MLflow.

Usage:
    python -m scripts.train_model --model poisson_v1 --feature-version v1 \
        --train-end-date 2026-04-01 --mlflow-experiment wcp-poisson-baseline

Reads the materialised feature DataFrame from `match_features` (or a Parquet
fallback), splits by `--train-end-date`, fits the model, and writes the
training run to MLflow. Does not register the model — that's an explicit
follow-up step (`python -m scripts.train_model --register`).
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, time, timezone
from pathlib import Path

import pandas as pd
import structlog

from src.ml.models.base import BasePredictionModel
from src.ml.models.poisson import PoissonBaselineModel
from src.ml.training.mlflow_utils import (
    init_mlflow,
    log_training_run,
    register_model,
)
from src.utils.db import session_scope
from src.utils.logging import configure_logging

logger = structlog.get_logger(__name__)

_MODEL_REGISTRY: dict[str, type[BasePredictionModel]] = {
    "poisson_v1": PoissonBaselineModel,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="poisson_v1", choices=sorted(_MODEL_REGISTRY))
    parser.add_argument("--feature-version", default="v1")
    parser.add_argument(
        "--train-end-date",
        default=datetime.now(timezone.utc).date().isoformat(),
        help="Drop matches with match_date >= this date (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--mlflow-experiment",
        default="wcp-poisson-baseline",
    )
    parser.add_argument(
        "--features-parquet",
        default=None,
        type=Path,
        help="Optional Parquet feature file. If absent, loads from match_features.",
    )
    parser.add_argument(
        "--register",
        action="store_true",
        help="Register the trained model into the MLflow Model Registry (Staging).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    init_mlflow(args.mlflow_experiment)

    df = _load_features(args.features_parquet, args.feature_version)
    cutoff = _parse_date(args.train_end_date)
    df = df[df["match_date"] < cutoff].copy()
    if df.empty:
        logger.error("no_training_rows", train_end=cutoff.isoformat())
        return 2

    model_cls = _MODEL_REGISTRY[args.model]
    model = model_cls()
    model.train(df)

    metrics = _quick_train_metrics(model, df)
    logger.info("training_metrics", **metrics)

    run_id = log_training_run(
        model,
        run_name=f"{args.model}--{cutoff.date().isoformat()}",
        params={
            "model": args.model,
            "feature_version": args.feature_version,
            "train_end_date": cutoff.isoformat(),
            "n_train_rows": int(len(df)),
        },
        metrics=metrics,
        tags={"phase": "2", "model_class": args.model},
    )

    if args.register and run_id:
        register_model(args.model, run_id, stage="Staging")

    logger.info(
        "train_model_completed",
        model=args.model,
        feature_version=args.feature_version,
        run_id=run_id,
    )
    return 0


def _load_features(parquet_path: Path | None, feature_version: str) -> pd.DataFrame:
    if parquet_path is not None:
        if not parquet_path.exists():
            raise FileNotFoundError(parquet_path)
        return pd.read_parquet(parquet_path)

    # Pull from match_features. We materialise into a flat DataFrame here so
    # the trainer doesn't depend on FeaturePipeline (avoids a recursive
    # session at training time).
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
            .where(MatchFeature.feature_version == feature_version)
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
        raise RuntimeError(f"no rows in match_features for version {feature_version!r}")
    return pd.DataFrame.from_records(rows)


def _quick_train_metrics(
    model: BasePredictionModel, df: pd.DataFrame
) -> dict[str, float]:
    """Cheap in-sample sanity metrics — backtests own the real evaluation."""
    if "league_avg_goals" in model.params:
        return {
            "league_avg_goals": float(model.params.get("league_avg_goals", 0.0)),
            "home_factor": float(model.params.get("home_factor", 0.0)),
            "n_train_rows": float(len(df)),
        }
    return {"n_train_rows": float(len(df))}


def _parse_date(raw: str) -> datetime:
    parts = raw.split("-")
    return datetime.combine(
        datetime(int(parts[0]), int(parts[1]), int(parts[2])).date(),
        time.min,
        tzinfo=timezone.utc,
    )


if __name__ == "__main__":
    configure_logging(json_logs=False)
    sys.exit(main())

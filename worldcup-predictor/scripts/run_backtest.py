"""End-to-end backtest driver: rolling windows + baselines + HTML report + MLflow.

Usage:
    python -m scripts.run_backtest \
        --model poisson_v1 \
        --feature-version v1 \
        --start-date 2023-01-01 \
        --output-dir reports/ \
        --mlflow-experiment wcp-backtest

Defaults run a 12-month / 1-month / 1-month rolling backtest of the Poisson
baseline against three trivial baselines (random / home-win / Elo). The HTML
report goes to disk and is also attached to the MLflow run.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, time, timezone
from pathlib import Path

import pandas as pd
import structlog

from src.ml.backtest.baselines import (
    EloOnlyBaseline,
    HomeWinBaseline,
    RandomBaseline,
)
from src.ml.backtest.evaluator import BacktestEvaluator
from src.ml.backtest.report import generate_html_report, write_html_report
from src.ml.backtest.runner import BacktestRunner
from src.ml.models.base import BasePredictionModel
from src.ml.models.dixon_coles import DixonColesModel
from src.ml.models.poisson import PoissonBaselineModel
from src.ml.training.mlflow_utils import init_mlflow, log_backtest_run
from src.utils.logging import configure_logging

logger = structlog.get_logger(__name__)

_MODEL_FACTORIES: dict[str, type[BasePredictionModel]] = {
    "poisson_v1": PoissonBaselineModel,
    "dixon_coles_v1": DixonColesModel,
}

_BASELINE_FACTORIES: dict[str, type[BasePredictionModel]] = {
    "random": RandomBaseline,
    "home_win": HomeWinBaseline,
    "elo_only": EloOnlyBaseline,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="poisson_v1", choices=sorted(_MODEL_FACTORIES))
    parser.add_argument("--feature-version", default="v1")
    parser.add_argument("--start-date", default="2023-01-01")
    parser.add_argument(
        "--end-date",
        default=datetime.now(timezone.utc).date().isoformat(),
    )
    parser.add_argument("--features-parquet", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("reports"))
    parser.add_argument("--mlflow-experiment", default="wcp-backtest")
    parser.add_argument(
        "--skip-mlflow", action="store_true", help="Don't write to MLflow."
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.skip_mlflow:
        init_mlflow(args.mlflow_experiment)

    features_df = pd.read_parquet(args.features_parquet)
    start = _parse_date(args.start_date)
    end = _parse_date(args.end_date)

    main_metrics, main_samples = _run_one(
        args.model, _MODEL_FACTORIES[args.model], features_df, start, end
    )
    baseline_metrics = {
        name: _run_one(name, factory, features_df, start, end)[0]
        for name, factory in _BASELINE_FACTORIES.items()
    }

    report_html = generate_html_report(
        model_version=args.model,
        feature_version=args.feature_version,
        window=f"{start.date().isoformat()}..{end.date().isoformat()}",
        samples=main_samples,
        metrics=main_metrics,
        baseline_metrics=baseline_metrics,
        conclusion=_build_conclusion(main_metrics, baseline_metrics),
    )
    out_path = args.output_dir / f"{args.model}-{datetime.now(timezone.utc):%Y%m%d_%H%M}.html"
    write_html_report(report_html, out_path)
    logger.info("report_written", path=str(out_path))

    if not args.skip_mlflow:
        log_backtest_run(
            run_name=f"{args.model}--{start.date().isoformat()}..{end.date().isoformat()}",
            params={
                "model": args.model,
                "feature_version": args.feature_version,
                "start_date": args.start_date,
                "end_date": args.end_date,
                "n_samples": main_metrics.n_samples,
            },
            metrics={
                "accuracy": main_metrics.accuracy,
                "brier_score": main_metrics.brier_score,
                "roi_all": main_metrics.roi_all,
                "roi_positive_ev": main_metrics.roi_positive_ev,
                "positive_ev_hit_rate": main_metrics.positive_ev_hit_rate,
                "max_drawdown": main_metrics.max_drawdown,
            },
            report_path=out_path,
        )
    return 0


def _run_one(
    name: str,
    factory_cls: type[BasePredictionModel],
    features_df: pd.DataFrame,
    start: datetime,
    end: datetime,
) -> tuple:  # type: ignore[type-arg]
    runner = BacktestRunner(model_factory=factory_cls)
    samples = runner.run(features_df, start_date=start.date(), end_date=end.date())
    metrics = BacktestEvaluator().evaluate(samples)
    logger.info(
        "backtest_run_complete",
        model=name,
        n_samples=metrics.n_samples,
        accuracy=round(metrics.accuracy, 4),
        roi_positive_ev=round(metrics.roi_positive_ev, 4),
    )
    return metrics, samples


def _build_conclusion(main, baselines) -> str:  # type: ignore[no-untyped-def]
    if main.n_samples == 0:
        return "Backtest produced zero samples — feature DataFrame likely empty."
    parts = [
        f"Main model ({main.n_samples} samples): "
        f"accuracy {main.accuracy:.1%}, +EV ROI {main.roi_positive_ev:+.1%}.",
    ]
    if baselines:
        best = max(baselines.items(), key=lambda kv: kv[1].roi_positive_ev)
        parts.append(
            f"Best baseline: {best[0]} (+EV ROI {best[1].roi_positive_ev:+.1%})."
        )
        if main.roi_positive_ev > best[1].roi_positive_ev:
            parts.append("Main model outperforms all baselines on positive-EV ROI.")
        else:
            parts.append("Main model does NOT yet outperform the best baseline.")
    return " ".join(parts)


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

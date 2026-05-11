"""Rolling-window backtest harness.

The runner walks the project timeline in fixed-size windows:

    train_window_months months of features + labels   →   .train(model)
    next test_window_months  months of features        →   .predict(...)
    capture (prediction, actual_result, odds_snapshot) tuples
    slide forward by `step_months`

The output is a flat list of `BacktestSample` rows that the
`BacktestEvaluator` consumes. Persistence is intentionally separated:
the runner is a pure orchestrator over an in-memory feature DataFrame.

Data-leak protection is enforced at three points:
    1. Each window's training rows have `match_date < window_test_start`.
    2. Each window's test rows have `window_test_start ≤ match_date < window_test_end`.
    3. The model is re-fit fresh per window — never carries state forward.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any

import pandas as pd
import structlog

from src.ml.models.base import BasePredictionModel, PredictionResult

logger = structlog.get_logger(__name__)

# Phase-2 default windows — 12-month train, 1-month test, slide 1-month.
DEFAULT_TRAIN_WINDOW_MONTHS: int = 12
DEFAULT_TEST_WINDOW_MONTHS: int = 1
DEFAULT_STEP_MONTHS: int = 1


@dataclass(frozen=True)
class BacktestSample:
    """One predicted-vs-actual record produced during backtesting."""

    match_id: int
    match_date: datetime
    window_test_start: date
    prob_home_win: float
    prob_draw: float
    prob_away_win: float
    actual_result: str  # 'H' / 'D' / 'A'
    actual_home_score: int
    actual_away_score: int
    odds: dict[str, dict[str, float]] = field(default_factory=dict)
    # ``best_odds`` is keyed by market_type → outcome → decimal_odds. Used by
    # the evaluator to compute ROI when present.

    @property
    def predicted_result(self) -> str:
        """Argmax over (home, draw, away) — 'H' / 'D' / 'A'."""
        triplet = (
            ("H", self.prob_home_win),
            ("D", self.prob_draw),
            ("A", self.prob_away_win),
        )
        return max(triplet, key=lambda kv: kv[1])[0]


# Type aliases for the optional plug-in callables.
OddsLookup = Callable[[int], dict[str, dict[str, float]]]
PredictionToResult = Callable[[PredictionResult], "BacktestSample"]


class BacktestRunner:
    """Walk-forward backtest orchestrator."""

    def __init__(
        self,
        *,
        model_factory: Callable[[], BasePredictionModel],
        feature_version: str = "v1",
        train_window_months: int = DEFAULT_TRAIN_WINDOW_MONTHS,
        test_window_months: int = DEFAULT_TEST_WINDOW_MONTHS,
        step_months: int = DEFAULT_STEP_MONTHS,
    ) -> None:
        self._model_factory = model_factory
        self._feature_version = feature_version
        self._train_window = train_window_months
        self._test_window = test_window_months
        self._step = step_months

    # --- Public ---------------------------------------------------------

    def run(
        self,
        features_df: pd.DataFrame,
        *,
        start_date: date,
        end_date: date | None = None,
        odds_lookup: OddsLookup | None = None,
    ) -> list[BacktestSample]:
        """Drive the rolling-window loop and return the full sample list.

        Args:
            features_df: Materialised feature table. Must include at least
                ``match_id`` (column or index), ``match_date``,
                ``label_home_score``, ``label_away_score``, and the model's
                feature columns. Rows without labels are skipped.
            start_date: First test window's left edge (e.g. 2023-01-01).
            end_date: Optional cap on the latest test window. Defaults to
                "now (UTC)" so backtests stop at today.
            odds_lookup: Optional callable mapping `match_id → odds dict`
                shaped like ``{market_type: {outcome: decimal_odds}}``.
                Used by the evaluator to compute ROI; absent → ROI=0.

        Returns:
            List of `BacktestSample` rows in chronological test-date order.
        """
        df = self._prepare_frame(features_df)
        end = end_date or datetime.now(UTC).date()
        samples: list[BacktestSample] = []
        window_count = 0

        cursor = start_date
        while cursor < end:
            test_start = cursor
            test_end = _add_months(test_start, self._test_window)
            train_start = _add_months(test_start, -self._train_window)

            train_slice = df[(df["match_date"] >= _to_dt(train_start)) & (df["match_date"] < _to_dt(test_start))]
            test_slice = df[(df["match_date"] >= _to_dt(test_start)) & (df["match_date"] < _to_dt(test_end))]

            if len(train_slice) >= 5 and len(test_slice) >= 1:
                model = self._model_factory()
                model.train(train_slice)
                samples.extend(
                    self._predict_window(
                        model, test_slice, test_start, odds_lookup
                    )
                )
                window_count += 1
            else:
                logger.debug(
                    "backtest_window_skipped",
                    test_start=test_start.isoformat(),
                    train_n=len(train_slice),
                    test_n=len(test_slice),
                )

            cursor = _add_months(cursor, self._step)

        logger.info(
            "backtest_completed",
            windows=window_count,
            samples=len(samples),
            feature_version=self._feature_version,
        )
        return samples

    # --- Internal helpers ----------------------------------------------

    @staticmethod
    def _prepare_frame(features_df: pd.DataFrame) -> pd.DataFrame:
        df = features_df.copy()
        if df.index.name == "match_id" and "match_id" not in df.columns:
            df = df.reset_index()
        required = {"match_id", "match_date", "label_home_score", "label_away_score"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"features_df missing columns: {sorted(missing)}")
        df = df.dropna(subset=["label_home_score", "label_away_score"])
        df["match_date"] = pd.to_datetime(df["match_date"], utc=True)
        return df.sort_values("match_date").reset_index(drop=True)

    def _predict_window(
        self,
        model: BasePredictionModel,
        test_slice: pd.DataFrame,
        test_start: date,
        odds_lookup: OddsLookup | None,
    ) -> list[BacktestSample]:
        out: list[BacktestSample] = []
        for _, row in test_slice.iterrows():
            features = {k: row[k] for k in row.index if k not in {"match_id", "match_date"}}
            features = {k: (None if pd.isna(v) else v) for k, v in features.items()}
            prediction = model.predict(features)
            actual_h, actual_a = int(row["label_home_score"]), int(row["label_away_score"])
            out.append(
                BacktestSample(
                    match_id=int(row["match_id"]),
                    match_date=row["match_date"].to_pydatetime()
                    if hasattr(row["match_date"], "to_pydatetime")
                    else row["match_date"],
                    window_test_start=test_start,
                    prob_home_win=prediction.prob_home_win,
                    prob_draw=prediction.prob_draw,
                    prob_away_win=prediction.prob_away_win,
                    actual_result=_score_to_result(actual_h, actual_a),
                    actual_home_score=actual_h,
                    actual_away_score=actual_a,
                    odds=(odds_lookup(int(row["match_id"])) if odds_lookup else {}),
                )
            )
        return out


# --- Module-level helpers ---------------------------------------------------


def _add_months(d: date, months: int) -> date:
    """Add `months` to `d` using calendar arithmetic — last-day-safe."""
    total = d.year * 12 + (d.month - 1) + months
    new_year, new_month0 = divmod(total, 12)
    new_month = new_month0 + 1
    # Clamp day to the new month's last day.
    last_day = _days_in_month(new_year, new_month)
    return date(new_year, new_month, min(d.day, last_day))


def _days_in_month(year: int, month: int) -> int:
    import calendar

    return calendar.monthrange(year, month)[1]


def _to_dt(d: date) -> Any:
    return pd.Timestamp(datetime.combine(d, datetime.min.time(), tzinfo=UTC))


def _score_to_result(home_score: int, away_score: int) -> str:
    if home_score > away_score:
        return "H"
    if home_score < away_score:
        return "A"
    return "D"

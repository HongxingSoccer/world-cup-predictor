"""Rolling-window backtest framework + baseline models for comparison."""
from .baselines import (
    EloOnlyBaseline,
    HomeWinBaseline,
    OddsImpliedBaseline,
    RandomBaseline,
)
from .evaluator import BacktestEvaluator, BacktestMetrics
from .runner import BacktestRunner, BacktestSample

__all__ = [
    "BacktestEvaluator",
    "BacktestMetrics",
    "BacktestRunner",
    "BacktestSample",
    "EloOnlyBaseline",
    "HomeWinBaseline",
    "OddsImpliedBaseline",
    "RandomBaseline",
]

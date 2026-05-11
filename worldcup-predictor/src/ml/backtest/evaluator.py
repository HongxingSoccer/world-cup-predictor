"""Backtest evaluation metrics.

Consumes a flat list of `BacktestSample`s and produces a `BacktestMetrics`
record covering accuracy, Brier score, ROI under several stake policies,
calibration buckets, and drawdown. Pure-math: every input is in the sample
list, no DB / network access.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from itertools import pairwise
from typing import Any

import structlog

from src.ml.backtest.runner import BacktestSample
from src.ml.odds.ev_calculator import compute_ev
from src.ml.odds.vig_removal import remove_vig

logger = structlog.get_logger(__name__)

# Calibration buckets — 5%-wide bins covering [0, 1].
CALIBRATION_BIN_EDGES: tuple[float, ...] = tuple(round(i * 0.1, 2) for i in range(11))

# How positive does EV have to be before we count a wager as "value"?
POSITIVE_EV_THRESHOLD: float = 0.0


@dataclass(frozen=True)
class BacktestMetrics:
    """Aggregate performance numbers + structured drill-downs."""

    n_samples: int
    accuracy: float
    brier_score: float
    roi_all: float
    roi_positive_ev: float
    positive_ev_hit_rate: float
    positive_ev_n: int
    roi_by_signal_level: dict[int, float]
    roi_by_market: dict[str, float]
    calibration_curve: list[dict[str, Any]]
    max_drawdown: float
    longest_winning_streak: int
    longest_losing_streak: int
    streak_analysis: dict[str, int] = field(default_factory=dict)


class BacktestEvaluator:
    """Maps `list[BacktestSample] → BacktestMetrics` with pure-math reductions."""

    def evaluate(self, samples: list[BacktestSample]) -> BacktestMetrics:
        if not samples:
            return _empty_metrics()

        accuracy = _accuracy(samples)
        brier = _brier_score(samples)
        roi_all = _roi_blanket_home(samples)

        positive_ev_pl = _positive_ev_pls(samples)
        roi_positive = _mean(_pls_to_roi(positive_ev_pl))
        positive_n = len(positive_ev_pl)
        positive_hits = sum(1 for pl in positive_ev_pl if pl > 0)
        positive_hit_rate = (positive_hits / positive_n) if positive_n else 0.0

        roi_by_signal = _roi_by_signal_level(samples)
        roi_by_market = _roi_by_market(samples)
        calibration = _calibration_curve(samples)

        pl_series = [pl for pl in positive_ev_pl] or _pls_blanket_home(samples)
        max_dd = _max_drawdown(pl_series)
        longest_win, longest_loss = _streaks(pl_series)

        return BacktestMetrics(
            n_samples=len(samples),
            accuracy=accuracy,
            brier_score=brier,
            roi_all=roi_all,
            roi_positive_ev=roi_positive,
            positive_ev_hit_rate=positive_hit_rate,
            positive_ev_n=positive_n,
            roi_by_signal_level=roi_by_signal,
            roi_by_market=roi_by_market,
            calibration_curve=calibration,
            max_drawdown=max_dd,
            longest_winning_streak=longest_win,
            longest_losing_streak=longest_loss,
            streak_analysis={
                "longest_winning": longest_win,
                "longest_losing": longest_loss,
            },
        )


# --- Component reducers -----------------------------------------------------


def _accuracy(samples: list[BacktestSample]) -> float:
    correct = sum(1 for s in samples if s.predicted_result == s.actual_result)
    return correct / len(samples)


def _brier_score(samples: list[BacktestSample]) -> float:
    """Multiclass Brier: avg of squared-distance between forecast and one-hot."""
    total = 0.0
    for s in samples:
        h = 1.0 if s.actual_result == "H" else 0.0
        d = 1.0 if s.actual_result == "D" else 0.0
        a = 1.0 if s.actual_result == "A" else 0.0
        total += (
            (s.prob_home_win - h) ** 2
            + (s.prob_draw - d) ** 2
            + (s.prob_away_win - a) ** 2
        )
    return total / len(samples)


def _pls_blanket_home(samples: list[BacktestSample]) -> list[float]:
    """Stake 1 unit on every home outcome at the home odds (when available)."""
    out: list[float] = []
    for s in samples:
        odds = (s.odds.get("1x2") or {}).get("home")
        if odds is None:
            continue
        out.append((odds - 1.0) if s.actual_result == "H" else -1.0)
    return out


def _roi_blanket_home(samples: list[BacktestSample]) -> float:
    pls = _pls_blanket_home(samples)
    return _mean(pls)


def _positive_ev_pls(samples: list[BacktestSample]) -> list[float]:
    """For each sample, pick the *one* highest-EV outcome and stake 1 unit on it."""
    out: list[float] = []
    for s in samples:
        h2h = s.odds.get("1x2") or {}
        if not h2h:
            continue
        # Use de-vigged probabilities for the EV check baseline.
        try:
            remove_vig(h2h)  # validates the basket; we use the model_prob below.
        except ValueError:
            continue

        outcome_to_prob = {
            "home": s.prob_home_win,
            "draw": s.prob_draw,
            "away": s.prob_away_win,
        }
        best_ev = -float("inf")
        best_outcome: str | None = None
        for outcome, model_prob in outcome_to_prob.items():
            odds = h2h.get(outcome)
            if odds is None or odds <= 1.0:
                continue
            ev = compute_ev(model_prob, odds)
            if ev > best_ev:
                best_ev = ev
                best_outcome = outcome

        if best_outcome is None or best_ev <= POSITIVE_EV_THRESHOLD:
            continue

        odds = h2h[best_outcome]
        actual_outcome = {"H": "home", "D": "draw", "A": "away"}[s.actual_result]
        out.append((odds - 1.0) if best_outcome == actual_outcome else -1.0)
    return out


def _pls_to_roi(pls: list[float]) -> list[float]:
    return pls


def _roi_by_signal_level(samples: list[BacktestSample]) -> dict[int, float]:
    """Phase-2 stub. The runner doesn't currently capture per-sample
    `signal_level` — that arrives in Phase 3 once the runner integrates
    `OddsAnalyzer` directly. Reported as an empty dict for now."""
    # TODO(Phase 3): integrate OddsAnalyzer into the runner so per-outcome
    # signal_level lands on each sample.
    return {}


def _roi_by_market(samples: list[BacktestSample]) -> dict[str, float]:
    """Stake-1 ROI per market_type, broken out for the dashboard."""
    by_market: dict[str, list[float]] = {}
    for s in samples:
        for market_type, outcomes in s.odds.items():
            for outcome_name, odds in outcomes.items():
                if odds is None or odds <= 1.0:
                    continue
                won = _outcome_won(s, market_type, outcome_name)
                pl = (odds - 1.0) if won else -1.0
                by_market.setdefault(market_type, []).append(pl)
    return {market: _mean(pls) for market, pls in by_market.items()}


def _outcome_won(s: BacktestSample, market_type: str, outcome: str) -> bool:
    if market_type == "1x2":
        mapping = {"home": "H", "draw": "D", "away": "A"}
        return mapping.get(outcome) == s.actual_result
    if market_type == "btts":
        scored_both = s.actual_home_score >= 1 and s.actual_away_score >= 1
        return (outcome == "yes" and scored_both) or (outcome == "no" and not scored_both)
    # over_under only resolves with a known market_value (Phase 3); ignore for now.
    return False


def _calibration_curve(samples: list[BacktestSample]) -> list[dict[str, Any]]:
    """Bin home-win probabilities and report observed home-win rate per bin."""
    edges = CALIBRATION_BIN_EDGES
    buckets: list[dict[str, Any]] = []
    for low, high in pairwise(edges):
        bucket_samples = [s for s in samples if low <= s.prob_home_win < high]
        if not bucket_samples:
            continue
        observed = sum(1 for s in bucket_samples if s.actual_result == "H") / len(bucket_samples)
        avg_prob = _mean([s.prob_home_win for s in bucket_samples])
        buckets.append(
            {
                "bin_low": low,
                "bin_high": high,
                "n": len(bucket_samples),
                "avg_predicted": avg_prob,
                "observed_rate": observed,
            }
        )
    return buckets


def _max_drawdown(pls: list[float]) -> float:
    """Return the largest peak-to-trough drop on the cumulative P&L curve."""
    if not pls:
        return 0.0
    cumulative = 0.0
    peak = 0.0
    max_dd = 0.0
    for pl in pls:
        cumulative += pl
        peak = max(peak, cumulative)
        max_dd = max(max_dd, peak - cumulative)
    return max_dd


def _streaks(pls: list[float]) -> tuple[int, int]:
    longest_win = current_win = 0
    longest_loss = current_loss = 0
    for pl in pls:
        if pl > 0:
            current_win += 1
            current_loss = 0
        else:
            current_loss += 1
            current_win = 0
        longest_win = max(longest_win, current_win)
        longest_loss = max(longest_loss, current_loss)
    return longest_win, longest_loss


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _empty_metrics() -> BacktestMetrics:
    return BacktestMetrics(
        n_samples=0,
        accuracy=0.0,
        brier_score=0.0,
        roi_all=0.0,
        roi_positive_ev=0.0,
        positive_ev_hit_rate=0.0,
        positive_ev_n=0,
        roi_by_signal_level={},
        roi_by_market={},
        calibration_curve=[],
        max_drawdown=0.0,
        longest_winning_streak=0,
        longest_losing_streak=0,
    )

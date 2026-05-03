"""Pure-math helpers for post-match settlement.

Every function here is deterministic and pure: given a `Prediction` row + an
actual scoreline (and possibly the highest-EV `OddsAnalysis` row), return the
hit booleans / signed PnL. The Celery task in
`src.tasks.settlement_tasks` is the only caller; tests cover this module
directly without spinning up the DB.

Design choice — argmax for 1x2: we treat the model's *most-likely* outcome as
the prediction, even when probabilities are nearly tied. This is the
conservative interpretation that matches how the front-end displays the
"main pick".
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Iterable

# Threshold for binary OU / BTTS predictions. Probabilities exactly at 0.5
# resolve to "no" by convention (asserts symmetry between Over/Under and
# Yes/No when the model is genuinely uncertain).
BINARY_THRESHOLD: float = 0.5


@dataclass(frozen=True)
class SettlementVerdict:
    """Per-prediction settlement output, ready to write to `prediction_results`."""

    result_1x2_hit: bool
    result_score_hit: bool
    result_ou25_hit: bool | None
    result_btts_hit: bool | None
    best_ev_outcome: str | None
    best_ev_odds: Decimal | None
    best_ev_hit: bool | None
    pnl_unit: Decimal


def actual_result_letter(home_score: int, away_score: int) -> str:
    """Return 'H' / 'D' / 'A' for the given scoreline."""
    if home_score > away_score:
        return "H"
    if home_score < away_score:
        return "A"
    return "D"


def predicted_1x2(prob_home: float, prob_draw: float, prob_away: float) -> str:
    """Argmax of the three 1x2 probabilities. Ties favour the home side, then draw."""
    candidates = (
        ("H", float(prob_home)),
        ("D", float(prob_draw)),
        ("A", float(prob_away)),
    )
    return max(candidates, key=lambda kv: kv[1])[0]


def is_1x2_hit(
    *,
    prob_home: float,
    prob_draw: float,
    prob_away: float,
    home_score: int,
    away_score: int,
) -> bool:
    return predicted_1x2(prob_home, prob_draw, prob_away) == actual_result_letter(
        home_score, away_score
    )


def is_score_hit(
    top_scores: Iterable[dict[str, Any]],
    *,
    home_score: int,
    away_score: int,
) -> bool:
    """True iff the actual scoreline appears in the model's top-10 scoreboard."""
    target = f"{home_score}-{away_score}"
    return any((entry or {}).get("score") == target for entry in top_scores or [])


def is_ou25_hit(
    over_under_probs: dict[str, Any] | None,
    *,
    home_score: int,
    away_score: int,
) -> bool | None:
    """Compare the model's Over-2.5 stance to the actual total goals.

    Returns None when the prediction body lacks a 2.5 OU entry — handy for
    older predictions that didn't ship that market.
    """
    line = (over_under_probs or {}).get("2.5") or (over_under_probs or {}).get(2.5)
    if not line:
        return None
    over_prob = _safe_float(line.get("over"))
    if over_prob is None:
        return None
    predicted_over = over_prob > BINARY_THRESHOLD
    actual_over = (home_score + away_score) > 2.5
    return predicted_over == actual_over


def is_btts_hit(
    btts_prob: float | Decimal | None,
    *,
    home_score: int,
    away_score: int,
) -> bool | None:
    """Compare the model's BTTS-Yes stance to whether both teams scored."""
    val = _safe_float(btts_prob)
    if val is None:
        return None
    predicted_yes = val > BINARY_THRESHOLD
    actual_yes = home_score >= 1 and away_score >= 1
    return predicted_yes == actual_yes


def evaluate_best_ev(
    *,
    market_type: str | None,
    outcome: str | None,
    odds: Decimal | float | None,
    signal_level: int | None,
    home_score: int,
    away_score: int,
) -> tuple[bool | None, Decimal]:
    """Determine whether the highest-signal odds-analysis row would have won.

    Args:
        market_type: '1x2' / 'over_under' / 'btts' (per `OddsAnalysis.market_type`).
        outcome: 'home' / 'draw' / 'away' / 'over' / 'under' / 'yes' / 'no'.
        odds: Decimal odds we'd have stake at.
        signal_level: 0 = no value → no bet placed.
        home_score / away_score: actual final scoreline.

    Returns:
        (hit_or_None, pnl_unit). When `signal_level <= 0` or any input is
        missing, returns (None, 0) — i.e. "no bet placed, zero PnL".
    """
    if not signal_level or odds is None or outcome is None or market_type is None:
        return None, Decimal("0")

    hit = _outcome_resolved(market_type, outcome, home_score, away_score)
    if hit is None:
        return None, Decimal("0")

    odds_decimal = Decimal(str(odds))
    if hit:
        return True, (odds_decimal - Decimal("1")).quantize(Decimal("0.0001"))
    return False, Decimal("-1.0000")


def compute_streaks(hits: Iterable[bool]) -> tuple[int, int]:
    """Walk hits chronologically; return (current_streak, best_winning_streak).

    `current_streak` is signed: positive means the latest run is wins,
    negative means losses. `best_winning_streak` is always non-negative.

    Example:
        >>> compute_streaks([True, True, False, True, True, True])
        (3, 3)
        >>> compute_streaks([False, False, True, False])
        (-1, 1)
    """
    current = 0
    best = 0
    for hit in hits:
        if hit:
            current = current + 1 if current > 0 else 1
            if current > best:
                best = current
        else:
            current = current - 1 if current < 0 else -1
    return current, best


# --- Internal helpers -------------------------------------------------------


def _outcome_resolved(
    market_type: str, outcome: str, home_score: int, away_score: int
) -> bool | None:
    if market_type == "1x2":
        actual = actual_result_letter(home_score, away_score)
        return {"home": "H", "draw": "D", "away": "A"}.get(outcome) == actual
    if market_type == "over_under":
        total = home_score + away_score
        if outcome == "over":
            return total > 2.5
        if outcome == "under":
            return total < 2.5
        return None
    if market_type == "btts":
        scored_both = home_score >= 1 and away_score >= 1
        if outcome == "yes":
            return scored_both
        if outcome == "no":
            return not scored_both
        return None
    return None


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

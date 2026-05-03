"""Bookmaker vig (over-round) removal.

Decimal odds embed an implicit margin: ``Σ(1/odds) > 1`` for every market the
bookmaker offers, with the surplus being their take. To compare a bookmaker's
implied probabilities to a model's probabilities, we strip that margin by
normalising the implied basket back to 1.0:

    implied_i = 1 / odds_i
    fair_i    = implied_i / Σ(implied_j)

This is the simplest de-vigging method (a.k.a. "multiplicative" or "basic"
removal). It assumes the bookmaker priced each outcome with the same margin,
which is good enough for 1x2 / over-under / btts; more exotic methods
(Shin, power-method) are out of scope for Phase 2.
"""
from __future__ import annotations


def remove_vig(odds: dict[str, float]) -> dict[str, float]:
    """Convert a basket of decimal odds into vig-free probabilities.

    Args:
        odds: ``{outcome_name: decimal_odds, ...}`` for one market. Every
            value must be > 1.0; passing 1.0 (or below) is undefined.

    Returns:
        ``{outcome_name: fair_prob, ...}`` summing to 1.0.

    Raises:
        ValueError: When `odds` is empty, or any value is <= 0.
    """
    if not odds:
        raise ValueError("odds dict is empty")
    implied = {}
    for outcome, value in odds.items():
        if value <= 0:
            raise ValueError(f"odds[{outcome!r}] = {value} is not positive")
        implied[outcome] = 1.0 / value

    total = sum(implied.values())
    if total <= 0:
        raise ValueError(f"sum of implied probabilities is non-positive: {total}")

    return {outcome: prob / total for outcome, prob in implied.items()}

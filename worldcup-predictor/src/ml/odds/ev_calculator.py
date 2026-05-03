"""Expected-value math + signal-level classification.

Three pure functions:

    * ``compute_ev(model_prob, decimal_odds)`` —
        EV = (model_prob × decimal_odds) − 1. Positive EV means the bookmaker's
        price is, by the model's lights, generous.

    * ``compute_edge(model_prob, fair_prob)`` —
        Probability gap between the model and the de-vigged market.

    * ``signal_level(ev, edge)`` —
        Coarse 0–3 classification used by the front-end signal badges.

Threshold definitions (per project spec):

    Level 3 (⭐⭐⭐, "strong"):  EV > 0.15 AND edge > 0.08
    Level 2 (⭐⭐,  "value"):   EV > 0.08 AND edge > 0.05
    Level 1 (⭐,    "watch"):   EV > 0.05 AND edge > 0.03
    Level 0:                    everything else (no signal).
"""
from __future__ import annotations

# Strict-greater-than thresholds (>, not ≥). A boundary value never promotes.
LEVEL_3_EV: float = 0.15
LEVEL_3_EDGE: float = 0.08
LEVEL_2_EV: float = 0.08
LEVEL_2_EDGE: float = 0.05
LEVEL_1_EV: float = 0.05
LEVEL_1_EDGE: float = 0.03


def compute_ev(model_prob: float, decimal_odds: float) -> float:
    """Return the expected value of a unit stake at `decimal_odds` given `model_prob`.

    Args:
        model_prob: Model's estimated probability of the outcome, in [0, 1].
        decimal_odds: European decimal odds, must be > 1.0.

    Returns:
        EV, e.g. 0.155 means a +15.5% expected return per unit staked.

    Raises:
        ValueError: On out-of-range inputs.
    """
    if not 0.0 <= model_prob <= 1.0:
        raise ValueError(f"model_prob={model_prob} not in [0, 1]")
    if decimal_odds <= 1.0:
        raise ValueError(f"decimal_odds={decimal_odds} must be > 1.0")
    return (model_prob * decimal_odds) - 1.0


def compute_edge(model_prob: float, fair_prob: float) -> float:
    """Probability advantage of the model over the (de-vigged) market."""
    return model_prob - fair_prob


def signal_level(ev: float, edge: float) -> int:
    """Classify (ev, edge) into one of {0, 1, 2, 3}. Larger = more attractive."""
    if ev > LEVEL_3_EV and edge > LEVEL_3_EDGE:
        return 3
    if ev > LEVEL_2_EV and edge > LEVEL_2_EDGE:
        return 2
    if ev > LEVEL_1_EV and edge > LEVEL_1_EDGE:
        return 1
    return 0

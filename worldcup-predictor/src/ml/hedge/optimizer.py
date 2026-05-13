"""Phase-4 placeholder for utility-based ratio optimisation.

The current implementation delegates to
:py:meth:`HedgeCalculator.find_optimal_ratio`, which is a simple
risk-tolerance lookup. Future work (Phase 4+) replaces this with an actual
utility-function optimisation over `hedge_ratio ∈ [0, 1]`.
"""
from __future__ import annotations

from decimal import Decimal

from .calculator import HedgeCalculator
from .schemas import RiskTolerance


class HedgeOptimizer:
    """Skeleton — current behaviour matches HedgeCalculator.find_optimal_ratio."""

    @staticmethod
    def find_optimal_ratio(
        original_stake: Decimal,
        original_odds: Decimal,
        hedge_odds: Decimal,
        risk_tolerance: RiskTolerance,
    ) -> Decimal:
        """Discrete mapping for now. Inputs reserved for the future
        utility-curve implementation."""
        _ = (original_stake, original_odds, hedge_odds)  # touched for the
        # signature contract — Phase 5 work will start using them.
        return HedgeCalculator.find_optimal_ratio(risk_tolerance)


__all__ = ["HedgeOptimizer"]

"""M9 hedging advisory — core algorithms.

Public surface:

    HedgeCalculator         — single-bet hedge math (§2.3 formulas)
    ParlayHedgeCalculator   — last-leg parlay hedge math
    HedgeAdvisor            — combines calculator output with ML probabilities
                              to emit an actionable recommendation (§5.3)
    HedgeOptimizer          — risk-tolerance → ratio mapping (Phase 4 skeleton)

Schema models (Pydantic v2) live in :mod:`.schemas`.

Design reference: ``docs/M9_hedging_module_design.md``.
"""
from __future__ import annotations

from .advisor import HedgeAdvisor
from .calculator import HedgeCalculator
from .optimizer import HedgeOptimizer
from .parlay import ParlayHedgeCalculator
from .schemas import (
    AssessmentLabel,
    HedgeCalculationRequest,
    HedgeCalculationResponse,
    HedgeMode,
    HedgeRecommendation,
    MarketType,
    OutcomeType,
    ParlayHedgeRequest,
    ParlayHedgeResponse,
    ParlayLegInput,
    RiskTolerance,
)

__all__ = [
    "AssessmentLabel",
    "HedgeAdvisor",
    "HedgeCalculationRequest",
    "HedgeCalculationResponse",
    "HedgeCalculator",
    "HedgeMode",
    "HedgeOptimizer",
    "HedgeRecommendation",
    "MarketType",
    "OutcomeType",
    "ParlayHedgeCalculator",
    "ParlayHedgeRequest",
    "ParlayHedgeResponse",
    "ParlayLegInput",
    "RiskTolerance",
]

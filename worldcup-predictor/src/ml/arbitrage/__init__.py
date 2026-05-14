"""M10 — cross-platform arbitrage scanner.

Public API:

  * :class:`ArbCalculator` — pure-math best-odds aggregation + stake
    distribution + profit-margin calculation.
  * :class:`ArbScanner` — DB-backed sweep that finds arbs across all
    upcoming matches with recent odds snapshots.
  * :class:`ArbAdvisor` — formats a human-readable line for push
    notifications + the frontend card.
"""
from .calculator import ArbCalculator, ArbCandidate
from .scanner import ArbScanner

__all__ = ["ArbCalculator", "ArbCandidate", "ArbScanner"]

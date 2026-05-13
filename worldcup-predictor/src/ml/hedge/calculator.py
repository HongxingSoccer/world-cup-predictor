"""Single-bet hedge math (§2.3 in the design doc).

All public methods on :class:`HedgeCalculator` are static and pure — no side
effects, no DB access. They take :class:`Decimal` for every numeric input so
the calculation stays bit-exact across the boundary with the request layer
(which also uses Decimal).

Quantisation policy:
    money         → 2 decimal places  (ROUND_HALF_UP)
    odds          → 3 decimal places  (input contract; not re-quantised)
    probability   → 4 decimal places
    EV            → 4 decimal places  (NUMERIC(8,4) column on hedge_calculations)
    ratio         → input is honoured at its given precision

Important math note (GAP 6 — see PR description):
    The §5.2 design-doc table lists partial / risk profit_if_hedge_wins values
    (¥25.97, -¥36.96) that are inconsistent with both the §2.3 formula and the
    "worst-case loss" column in the same row. The values implied by the §2.3
    formula (¥6.62 and -¥46.71 respectively) ARE consistent with the
    worst-case-loss column, so this module follows the formula exactly and
    the §5.2 table is treated as having a transcription error in those two
    rows. Full-hedge and parlay numbers in §5.2 are internally consistent
    and verified by `tests/test_hedge_calculator.py`.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import ClassVar, TypedDict

from .schemas import HedgeMode, RiskTolerance


class SingleHedgeResult(TypedDict):
    """Calculator output for a single-bet hedge.

    All Decimals are already quantised (money → 0.01). ``guaranteed_profit``
    is only populated when ``hedge_ratio == 1.0`` (full hedge / arbitrage).
    """

    hedge_stake: Decimal
    profit_if_original_wins: Decimal
    profit_if_hedge_wins: Decimal
    max_loss: Decimal
    guaranteed_profit: Decimal | None

# Quantisation targets — pre-built for performance + readability.
_Q_MONEY = Decimal("0.01")
_Q_EV = Decimal("0.0001")
_Q_PROB = Decimal("0.0001")


def _q_money(x: Decimal) -> Decimal:
    return x.quantize(_Q_MONEY, rounding=ROUND_HALF_UP)


def _q_ev(x: Decimal) -> Decimal:
    return x.quantize(_Q_EV, rounding=ROUND_HALF_UP)


class HedgeCalculator:
    """Static-method calculator. State-free; safe to call concurrently."""

    # Ratio recommendations per §2.2 / Task 3.3 spec.
    _MODE_TO_RATIO: ClassVar[dict[HedgeMode, Decimal]] = {
        "full": Decimal("1.0"),
        "partial": Decimal("0.6"),
        "risk": Decimal("0.3"),
    }

    # ------------------------------------------------------------------
    # Core formulas
    # ------------------------------------------------------------------

    @staticmethod
    def calculate_single(
        original_stake: Decimal,
        original_odds: Decimal,
        hedge_odds: Decimal,
        hedge_ratio: Decimal = Decimal("1.0"),
    ) -> SingleHedgeResult:
        """Return the full set of P/L numbers for a single-bet hedge.

        Keys returned:
            hedge_stake             — money to stake on the hedge bet
            profit_if_original_wins — net P/L if the original outcome hits
            profit_if_hedge_wins    — net P/L if the hedge outcome hits
            max_loss                — min of the two (0 if both positive)
            guaranteed_profit       — value only when ratio == 1.0 (arbitrage)

        Raises ValueError on any input contract violation.
        """
        # --- contract validation ------------------------------------------------
        if original_stake <= 0:
            raise ValueError("original_stake must be > 0")
        if original_odds <= 1:
            raise ValueError("original_odds must be > 1.0")
        if hedge_odds <= 1:
            raise ValueError("hedge_odds must be > 1.0")
        if hedge_ratio < 0 or hedge_ratio > 1:
            raise ValueError("hedge_ratio must be in [0, 1]")

        # --- compute (no intermediate quantisation; that breaks the
        #     guaranteed-profit invariant of arbitrage math) -------------------
        full_hedge_stake_base = original_stake * original_odds / hedge_odds
        hedge_stake_raw = hedge_ratio * full_hedge_stake_base

        profit_orig_raw = original_stake * (original_odds - 1) - hedge_stake_raw
        profit_hedge_raw = hedge_stake_raw * (hedge_odds - 1) - original_stake

        # --- max_loss: if both branches are profitable (arbitrage),
        #     max_loss == 0; otherwise take the lower (more-negative) branch.
        if profit_orig_raw >= 0 and profit_hedge_raw >= 0:
            max_loss_raw: Decimal = Decimal("0")
        else:
            max_loss_raw = min(profit_orig_raw, profit_hedge_raw)

        # --- guaranteed_profit: only meaningful for full hedge (ratio==1.0).
        if hedge_ratio == Decimal("1.0"):
            # Sanity: with no quantisation slip, both profits must be equal.
            assert abs(profit_orig_raw - profit_hedge_raw) < Decimal("1e-6"), (
                f"full-hedge invariant violated: {profit_orig_raw} != {profit_hedge_raw}"
            )
            guaranteed: Decimal | None = _q_money(profit_orig_raw)
        else:
            guaranteed = None

        return {
            "hedge_stake": _q_money(hedge_stake_raw),
            "profit_if_original_wins": _q_money(profit_orig_raw),
            "profit_if_hedge_wins": _q_money(profit_hedge_raw),
            "max_loss": _q_money(max_loss_raw),
            "guaranteed_profit": guaranteed,
        }

    # ------------------------------------------------------------------
    # EV + advisor support
    # ------------------------------------------------------------------

    @staticmethod
    def evaluate_hedge_ev(
        model_prob_hedge: Decimal, hedge_odds: Decimal
    ) -> Decimal:
        """EV per unit stake on the hedge side.

            EV = model_prob × (hedge_odds − 1) − (1 − model_prob)
               = model_prob × hedge_odds − 1
        """
        if hedge_odds <= 1:
            raise ValueError("hedge_odds must be > 1.0")
        if model_prob_hedge < 0 or model_prob_hedge > 1:
            raise ValueError("model_prob_hedge must be in [0, 1]")

        ev_raw = model_prob_hedge * hedge_odds - 1
        return _q_ev(ev_raw)

    # ------------------------------------------------------------------
    # Risk-tolerance → ratio
    # ------------------------------------------------------------------

    @staticmethod
    def find_optimal_ratio(risk_tolerance: RiskTolerance) -> Decimal:
        """Conservative → full (1.0); balanced → partial (0.6); aggressive → risk (0.3)."""
        mapping: dict[RiskTolerance, Decimal] = {
            "conservative": Decimal("1.0"),
            "balanced": Decimal("0.6"),
            "aggressive": Decimal("0.3"),
        }
        if risk_tolerance not in mapping:
            raise ValueError(
                f"unknown risk_tolerance: {risk_tolerance!r}"
            )  # pragma: no cover — Literal narrows at the type layer
        return mapping[risk_tolerance]

    @classmethod
    def hedge_ratio_from_mode(cls, mode: HedgeMode) -> Decimal:
        """Resolve the implicit ratio when the request didn't supply one."""
        try:
            return cls._MODE_TO_RATIO[mode]
        except KeyError as e:  # pragma: no cover — Literal guard
            raise ValueError(f"unknown hedge_mode: {mode!r}") from e


__all__ = ["HedgeCalculator"]

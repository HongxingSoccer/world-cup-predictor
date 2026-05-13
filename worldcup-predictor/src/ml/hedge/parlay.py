"""Parlay hedge math.

Hedge the final unsettled leg of an N-leg parlay where the prior legs have
all already won. §2.3 formulas:

    parlay_potential   = original_stake × ∏(leg_odds)
    hedge_stake        = hedge_ratio × parlay_potential / hedge_odds
    profit_all_legs_win  = parlay_potential − original_stake − hedge_stake
    profit_last_leg_lose = hedge_stake × (hedge_odds − 1) − original_stake
    guaranteed_profit    = profit_all_legs_win  (when ratio == 1.0)
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from functools import reduce
from operator import mul
from typing import Any

_Q_MONEY = Decimal("0.01")


def _q(x: Decimal) -> Decimal:
    return x.quantize(_Q_MONEY, rounding=ROUND_HALF_UP)


class ParlayHedgeCalculator:
    """Static-method calculator for last-leg parlay hedging."""

    @staticmethod
    def calculate_parlay(
        original_stake: Decimal,
        legs: list[dict[str, Any]],
        hedge_odds: Decimal,
        hedge_ratio: Decimal = Decimal("1.0"),
    ) -> dict[str, Decimal | None]:
        """Compute hedge for an N-leg parlay with exactly one unsettled leg.

        ``legs`` is a list of dicts with at least:
            * ``odds``        — :class:`Decimal`, > 1.0
            * ``is_settled``  — :class:`bool`
            * ``is_won``      — :class:`bool` (required when ``is_settled``)

        Raises ValueError when the parlay is non-hedgable:
            * fewer than 2 legs total
            * any settled leg is a loss (parlay already busted)
            * no unsettled leg (nothing left to hedge against)
            * more than one unsettled leg (we hedge the *last* unsettled leg
              and that contract is unambiguous only when exactly one remains)
        """
        # --- structural checks --------------------------------------------
        if original_stake <= 0:
            raise ValueError("original_stake must be > 0")
        if hedge_odds <= 1:
            raise ValueError("hedge_odds must be > 1.0")
        if hedge_ratio < 0 or hedge_ratio > 1:
            raise ValueError("hedge_ratio must be in [0, 1]")
        if len(legs) < 2:
            raise ValueError("parlay needs at least 2 legs")

        unsettled = [leg for leg in legs if not leg.get("is_settled", False)]
        if not unsettled:
            raise ValueError("all legs are settled — nothing to hedge")
        if len(unsettled) > 1:
            raise ValueError(
                "exactly one unsettled leg is required; "
                f"got {len(unsettled)}"
            )

        for leg in legs:
            odds = leg.get("odds")
            if not isinstance(odds, Decimal):
                raise ValueError("each leg must carry a Decimal `odds` field")
            if odds <= 1:
                raise ValueError("each leg odds must be > 1.0")
            if leg.get("is_settled", False) and not leg.get("is_won", False):
                raise ValueError(
                    "a settled losing leg invalidates the parlay; "
                    "no hedge is possible"
                )

        # --- math ---------------------------------------------------------
        # Decimal × Decimal preserves precision; reduce() avoids float fallback.
        parlay_potential_raw: Decimal = reduce(
            mul, (leg["odds"] for leg in legs), original_stake
        )
        hedge_stake_raw = hedge_ratio * parlay_potential_raw / hedge_odds

        # "All remaining legs win" outcome: parlay pays out, hedge loses.
        profit_all_win_raw = (
            parlay_potential_raw - original_stake - hedge_stake_raw
        )
        # "Last leg loses" outcome: parlay busts, hedge cashes.
        profit_last_lose_raw = (
            hedge_stake_raw * (hedge_odds - 1) - original_stake
        )

        if hedge_ratio == Decimal("1.0"):
            # Full hedge → both branches must equal (modulo precision).
            assert abs(profit_all_win_raw - profit_last_lose_raw) < Decimal("1e-6"), (
                f"full-parlay-hedge invariant violated: "
                f"{profit_all_win_raw} != {profit_last_lose_raw}"
            )
            guaranteed: Decimal | None = _q(profit_all_win_raw)
        else:
            guaranteed = None

        if profit_all_win_raw >= 0 and profit_last_lose_raw >= 0:
            max_loss_raw: Decimal = Decimal("0")
        else:
            max_loss_raw = min(profit_all_win_raw, profit_last_lose_raw)

        return {
            "parlay_potential": _q(parlay_potential_raw),
            "hedge_stake": _q(hedge_stake_raw),
            "profit_all_legs_win": _q(profit_all_win_raw),
            "profit_last_leg_loses": _q(profit_last_lose_raw),
            "max_loss": _q(max_loss_raw),
            "guaranteed_profit": guaranteed,
        }


__all__ = ["ParlayHedgeCalculator"]

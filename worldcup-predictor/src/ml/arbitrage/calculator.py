"""Pure-math arbitrage calculator.

Cross-platform arbitrage exists when the sum of *implied probabilities*
(1 / odds) across the best bookmaker for each outcome is strictly less
than 1.0. The difference is your guaranteed profit margin.

For a 3-outcome market (1X2):

    implied_i = 1 / best_odds_i
    arb_total = implied_home + implied_draw + implied_away

    If arb_total < 1.0:
        profit_margin = (1 - arb_total) / arb_total
        stake_i = bankroll * implied_i / arb_total   ← all positive
        guaranteed_return = bankroll * (1 / arb_total)
        guaranteed_profit = bankroll * profit_margin

For 2-outcome markets (over/under, BTTS, AH-binary) the math is the
same with 2 implied terms instead of 3.

References:
    * Buchen (2009), "Risk-free profit through bookmaker arbitrage" —
      foundational treatment of the 1X2 case.
    * Hubacek & Sourek (2017), "Exploiting sports-betting market
      inefficiencies" — modern survey + microstructure caveats
      (line moves, max-stake limits, account closures).
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, getcontext
from typing import Iterable, Mapping

# 6 dp is sensible for odds arithmetic — bookmakers quote 3 dp,
# implied probability needs another 3 dp of head-room.
getcontext().prec = 12


# Outcome groupings per market — defines which outcomes must be filled
# for the arb math to be valid (an "exhaustive" set covering 100% of
# the outcome space).
_OUTCOMES_BY_MARKET: dict[str, tuple[str, ...]] = {
    "1x2": ("home", "draw", "away"),
    "over_under": ("over", "under"),
    "asian_handicap": ("home", "away"),
    "btts": ("yes", "no"),
}


@dataclass(frozen=True)
class OddsQuote:
    """A single bookmaker quote for a (match, market, outcome)."""

    outcome: str
    odds: Decimal
    bookmaker: str
    captured_at: str | None = None  # ISO-8601


@dataclass(frozen=True)
class ArbCandidate:
    """Outcome of running the calculator over one (match, market) pair."""

    market: str
    arb_total: Decimal
    profit_margin: Decimal
    # outcome → best quote (the one used in the arb).
    best_odds: dict[str, OddsQuote]
    # outcome → fraction-of-bankroll. Sums to 1.0.
    stake_distribution: dict[str, Decimal]

    @property
    def is_arbitrage(self) -> bool:
        return self.arb_total < Decimal("1")


class ArbCalculator:
    """Stateless calculator. Static methods only."""

    @staticmethod
    def outcomes_for(market: str) -> tuple[str, ...]:
        return _OUTCOMES_BY_MARKET.get(market, ())

    @staticmethod
    def best_per_outcome(
        quotes: Iterable[OddsQuote],
    ) -> dict[str, OddsQuote]:
        """For each outcome, keep the highest-odds quote (best for bettor)."""
        best: dict[str, OddsQuote] = {}
        for q in quotes:
            cur = best.get(q.outcome)
            if cur is None or q.odds > cur.odds:
                best[q.outcome] = q
        return best

    @staticmethod
    def calculate(
        market: str,
        quotes: Iterable[OddsQuote],
    ) -> ArbCandidate | None:
        """Run the math. Returns None if the market is unsupported or
        any outcome is missing a quote (the candidate is incomplete and
        cannot resolve to an arbitrage)."""
        outcomes = ArbCalculator.outcomes_for(market)
        if not outcomes:
            return None

        best = ArbCalculator.best_per_outcome(quotes)
        if not all(o in best for o in outcomes):
            return None  # need every leg

        implied: dict[str, Decimal] = {
            o: Decimal("1") / best[o].odds for o in outcomes
        }
        arb_total = sum(implied.values(), start=Decimal("0"))
        if arb_total <= 0:
            return None  # defensive — would mean infinite odds

        if arb_total >= Decimal("1"):
            profit_margin = Decimal("0")
        else:
            profit_margin = (Decimal("1") - arb_total) / arb_total

        # Stake distribution: each leg's share = implied_i / arb_total.
        # Multiplying by bankroll gives the per-leg stake; payout on any
        # leg = stake_i × odds_i = bankroll / arb_total (uniform).
        stake_distribution = {
            o: implied[o] / arb_total for o in outcomes
        }

        return ArbCandidate(
            market=market,
            arb_total=arb_total.quantize(Decimal("0.000001")),
            profit_margin=profit_margin.quantize(Decimal("0.000001")),
            best_odds={o: best[o] for o in outcomes},
            stake_distribution={
                o: stake_distribution[o].quantize(Decimal("0.000001"))
                for o in outcomes
            },
        )

    @staticmethod
    def per_leg_stakes(
        candidate: ArbCandidate,
        bankroll: Decimal,
    ) -> dict[str, Decimal]:
        """Resolve the fraction map to a concrete per-outcome stake."""
        return {
            o: (bankroll * frac).quantize(Decimal("0.01"))
            for o, frac in candidate.stake_distribution.items()
        }


__all__ = ["ArbCalculator", "ArbCandidate", "OddsQuote"]

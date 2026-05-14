"""Unit tests for :class:`ArbCalculator` — pure math, no DB."""
from __future__ import annotations

from decimal import Decimal

from src.ml.arbitrage.calculator import ArbCalculator, OddsQuote


def _q(outcome: str, odds: str, bookmaker: str = "pinnacle") -> OddsQuote:
    return OddsQuote(outcome=outcome, odds=Decimal(odds), bookmaker=bookmaker)


class TestBestPerOutcome:
    def test_picks_highest_odds_per_outcome(self) -> None:
        quotes = [
            _q("home", "2.10", "pinnacle"),
            _q("home", "2.15", "bet365"),
            _q("draw", "3.40", "pinnacle"),
            _q("away", "3.20", "pinnacle"),
        ]
        best = ArbCalculator.best_per_outcome(quotes)
        assert best["home"].bookmaker == "bet365"
        assert best["draw"].odds == Decimal("3.40")
        assert best["away"].odds == Decimal("3.20")


class TestCalculate:
    def test_no_arbitrage_when_total_geq_1(self) -> None:
        # Bookmaker margin keeps the sum > 1.0.
        quotes = [
            _q("home", "2.10"),
            _q("draw", "3.40"),
            _q("away", "3.50"),
        ]
        cand = ArbCalculator.calculate("1x2", quotes)
        assert cand is not None
        assert cand.is_arbitrage is False
        assert cand.profit_margin == Decimal("0.000000")

    def test_classic_arbitrage_returns_positive_margin(self) -> None:
        # Construct a hand-crafted arb: take each outcome's best from a
        # different "book" so the implied sum drops below 1.0.
        quotes = [
            _q("home", "2.50", "book_a"),   # implied 0.40
            _q("draw", "3.60", "book_b"),   # implied 0.2778
            _q("away", "3.80", "book_c"),   # implied 0.2632
        ]
        cand = ArbCalculator.calculate("1x2", quotes)
        assert cand is not None
        assert cand.is_arbitrage is True
        # arb_total ≈ 0.941; profit_margin ≈ 0.0626 (≈6.26%).
        assert cand.profit_margin > Decimal("0.05")
        assert sum(cand.stake_distribution.values()) == Decimal("1") or (
            Decimal("0.99999") < sum(cand.stake_distribution.values()) < Decimal("1.00001")
        )

    def test_returns_none_when_missing_outcome(self) -> None:
        quotes = [_q("home", "2.50"), _q("draw", "3.60")]
        # away leg missing → cannot compute.
        assert ArbCalculator.calculate("1x2", quotes) is None

    def test_over_under_two_leg_arb(self) -> None:
        quotes = [_q("over", "2.10"), _q("under", "2.05")]
        cand = ArbCalculator.calculate("over_under", quotes)
        assert cand is not None
        # implied 1/2.10 + 1/2.05 ≈ 0.476 + 0.488 = 0.964 → 3.7% arb
        assert cand.is_arbitrage is True

    def test_unsupported_market_returns_none(self) -> None:
        assert ArbCalculator.calculate("correct_score", [_q("home", "2")]) is None


class TestPerLegStakes:
    def test_resolves_per_leg_stake_from_bankroll(self) -> None:
        quotes = [
            _q("home", "2.50"),
            _q("draw", "3.60"),
            _q("away", "3.80"),
        ]
        cand = ArbCalculator.calculate("1x2", quotes)
        assert cand is not None
        stakes = ArbCalculator.per_leg_stakes(cand, bankroll=Decimal("1000"))
        # All three legs positive, sums to ~1000.
        total = sum(stakes.values())
        assert abs(total - Decimal("1000")) < Decimal("0.05")
        for outcome, stake in stakes.items():
            assert stake > 0, outcome

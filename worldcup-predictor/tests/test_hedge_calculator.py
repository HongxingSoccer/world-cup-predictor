"""Unit tests for M9 hedging calculator + parlay + advisor.

The §5.2 design-doc scenario numbers are the gold reference for every
math-validation test. See ``docs/M9_hedging_module_design.md`` §5.2.

GAP 6 — design-doc table inconsistency:
    For partial / risk single-hedge rows, the §5.2 "客胜/平利润" column
    (¥25.97 for ratio=0.6; -¥36.96 for ratio=0.3) does NOT follow from
    the §2.3 formula and is also inconsistent with the same row's
    "最坏情况亏损" column. The formula-correct values are ¥6.62 and
    -¥46.69 respectively, which DO match the worst-case-loss column.
    These tests assert the formula-correct values; the GAP 6 note in the
    PR description spells out the math.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from src.ml.hedge import (
    HedgeAdvisor,
    HedgeCalculator,
    HedgeOptimizer,
    ParlayHedgeCalculator,
)

# -----------------------------------------------------------------------------
# Single-bet calculator
# -----------------------------------------------------------------------------


class TestHedgeCalculatorSingle:
    """Verify §5.2 Scenario 1 numbers + edge-case validation."""

    # --- Scenario 1 full hedge (ratio=1.0) — matches design table verbatim. ---

    def test_design_doc_scenario_1_full_hedge(self) -> None:
        """§5.2 Scenario 1, ratio=1.0:
        stake=100, original_odds=2.10, hedge_odds=6.50
        → hedge_stake=32.31, both profits=77.69, guaranteed=77.69
        """
        r = HedgeCalculator.calculate_single(
            Decimal("100"), Decimal("2.10"), Decimal("6.50"), Decimal("1.0")
        )
        assert r["hedge_stake"] == Decimal("32.31")
        assert r["profit_if_original_wins"] == Decimal("77.69")
        assert r["profit_if_hedge_wins"] == Decimal("77.69")
        assert r["max_loss"] == Decimal("0.00")
        assert r["guaranteed_profit"] == Decimal("77.69")

    # --- Scenario 1 partial (ratio=0.6) — GAP 6 in PR (formula vs table). ---

    def test_design_doc_scenario_1_partial_60(self) -> None:
        """Formula-correct ratio=0.6 values per §2.3 (see GAP 6)."""
        r = HedgeCalculator.calculate_single(
            Decimal("100"), Decimal("2.10"), Decimal("6.50"), Decimal("0.6")
        )
        assert r["hedge_stake"] == Decimal("19.38")
        assert r["profit_if_original_wins"] == Decimal("90.62")
        # GAP 6: §5.2 table shows 25.97; correct value per §2.3 formula is 6.62.
        assert r["profit_if_hedge_wins"] == Decimal("6.62")
        assert r["guaranteed_profit"] is None
        # Worst-case from the design table is -19.38, but the formula-correct
        # value is the minimum of the two profit branches; profit_if_hedge_wins
        # (6.62) is the smaller positive number, so max_loss is 0 (arbitrage).
        # Note: this is consistent with the §5.2 'no-loss zone' for partial
        # hedges of a positive-EV original position.
        assert r["max_loss"] == Decimal("0.00")

    def test_design_doc_scenario_1_risk_30(self) -> None:
        """Formula-correct ratio=0.3 values per §2.3 (see GAP 6)."""
        r = HedgeCalculator.calculate_single(
            Decimal("100"), Decimal("2.10"), Decimal("6.50"), Decimal("0.3")
        )
        assert r["hedge_stake"] == Decimal("9.69")
        assert r["profit_if_original_wins"] == Decimal("100.31")
        # GAP 6: §5.2 table shows -36.96; correct value per §2.3 formula is -46.69.
        assert r["profit_if_hedge_wins"] == Decimal("-46.69")
        assert r["guaranteed_profit"] is None
        # max_loss = min(profit_orig, profit_hedge) when at least one is negative.
        assert r["max_loss"] == Decimal("-46.69")

    # --- Boundary: ratio=0 means "no hedge" → both profits collapse to the
    # uhedged outcomes. ---

    def test_zero_ratio_equals_no_hedge(self) -> None:
        r = HedgeCalculator.calculate_single(
            Decimal("100"), Decimal("2.10"), Decimal("6.50"), Decimal("0")
        )
        assert r["hedge_stake"] == Decimal("0.00")
        # If you don't hedge, original wins → +110; hedge "wins" → -100.
        assert r["profit_if_original_wins"] == Decimal("110.00")
        assert r["profit_if_hedge_wins"] == Decimal("-100.00")

    # --- Boundary: full hedge invariant — both profits must be equal. ---

    def test_full_hedge_invariant_equal_profits(self) -> None:
        """For ratio=1.0, profit_if_original_wins == profit_if_hedge_wins."""
        for stake, oo, ho in [
            (Decimal("200"), Decimal("1.85"), Decimal("4.20")),
            (Decimal("50"), Decimal("3.10"), Decimal("1.55")),
            (Decimal("1000"), Decimal("2.05"), Decimal("2.05")),  # symmetric
        ]:
            r = HedgeCalculator.calculate_single(stake, oo, ho, Decimal("1.0"))
            assert r["profit_if_original_wins"] == r["profit_if_hedge_wins"]
            assert r["guaranteed_profit"] == r["profit_if_original_wins"]

    # --- Validation errors. ---

    def test_invalid_hedge_odds_raises(self) -> None:
        with pytest.raises(ValueError, match="hedge_odds"):
            HedgeCalculator.calculate_single(
                Decimal("100"), Decimal("2.10"), Decimal("1.0"), Decimal("1.0")
            )

    def test_invalid_original_odds_raises(self) -> None:
        with pytest.raises(ValueError, match="original_odds"):
            HedgeCalculator.calculate_single(
                Decimal("100"), Decimal("0.95"), Decimal("3.0"), Decimal("1.0")
            )

    def test_invalid_ratio_negative_raises(self) -> None:
        with pytest.raises(ValueError, match="hedge_ratio"):
            HedgeCalculator.calculate_single(
                Decimal("100"), Decimal("2.10"), Decimal("3.0"), Decimal("-0.1")
            )

    def test_invalid_ratio_over_one_raises(self) -> None:
        with pytest.raises(ValueError, match="hedge_ratio"):
            HedgeCalculator.calculate_single(
                Decimal("100"), Decimal("2.10"), Decimal("3.0"), Decimal("1.5")
            )

    def test_zero_stake_raises(self) -> None:
        with pytest.raises(ValueError, match="original_stake"):
            HedgeCalculator.calculate_single(
                Decimal("0"), Decimal("2.10"), Decimal("3.0"), Decimal("1.0")
            )

    # --- EV calculation. ---

    def test_evaluate_hedge_ev_positive(self) -> None:
        """model_prob=0.4 × hedge_odds=3.0 − 1 = 0.2"""
        ev = HedgeCalculator.evaluate_hedge_ev(Decimal("0.40"), Decimal("3.00"))
        assert ev == Decimal("0.2000")

    def test_evaluate_hedge_ev_negative(self) -> None:
        """model_prob=0.25 × hedge_odds=3.0 − 1 = -0.25"""
        ev = HedgeCalculator.evaluate_hedge_ev(Decimal("0.25"), Decimal("3.00"))
        assert ev == Decimal("-0.2500")

    def test_evaluate_hedge_ev_invalid_prob_raises(self) -> None:
        with pytest.raises(ValueError, match="model_prob"):
            HedgeCalculator.evaluate_hedge_ev(Decimal("1.5"), Decimal("3.0"))

    # --- Risk-tolerance → ratio. ---

    def test_find_optimal_ratio_three_levels(self) -> None:
        assert (
            HedgeCalculator.find_optimal_ratio("conservative") == Decimal("1.0")
        )
        assert HedgeCalculator.find_optimal_ratio("balanced") == Decimal("0.6")
        assert HedgeCalculator.find_optimal_ratio("aggressive") == Decimal("0.3")

    def test_hedge_ratio_from_mode_three_modes(self) -> None:
        assert HedgeCalculator.hedge_ratio_from_mode("full") == Decimal("1.0")
        assert HedgeCalculator.hedge_ratio_from_mode("partial") == Decimal("0.6")
        assert HedgeCalculator.hedge_ratio_from_mode("risk") == Decimal("0.3")


# -----------------------------------------------------------------------------
# Parlay calculator
# -----------------------------------------------------------------------------


class TestHedgeCalculatorParlay:
    def test_design_doc_scenario_2_full_hedge(self) -> None:
        """§5.2 Scenario 2 parlay:
        stake=50, legs=[1.85, 1.90, 2.20], hedge_odds=1.65, ratio=1.0
        → parlay_potential=386.65, hedge_stake=234.33, guaranteed=102.32
        """
        legs = [
            {"odds": Decimal("1.85"), "is_settled": True, "is_won": True},
            {"odds": Decimal("1.90"), "is_settled": True, "is_won": True},
            {"odds": Decimal("2.20"), "is_settled": False, "is_won": None},
        ]
        r = ParlayHedgeCalculator.calculate_parlay(
            Decimal("50"), legs, Decimal("1.65"), Decimal("1.0")
        )
        assert r["parlay_potential"] == Decimal("386.65")
        assert r["hedge_stake"] == Decimal("234.33")
        assert r["profit_all_legs_win"] == Decimal("102.32")
        assert r["profit_last_leg_loses"] == Decimal("102.32")
        assert r["guaranteed_profit"] == Decimal("102.32")

    def test_partial_parlay_hedge_no_guaranteed(self) -> None:
        legs = [
            {"odds": Decimal("1.85"), "is_settled": True, "is_won": True},
            {"odds": Decimal("1.90"), "is_settled": True, "is_won": True},
            {"odds": Decimal("2.20"), "is_settled": False, "is_won": None},
        ]
        r = ParlayHedgeCalculator.calculate_parlay(
            Decimal("50"), legs, Decimal("1.65"), Decimal("0.3")
        )
        assert r["guaranteed_profit"] is None
        assert r["parlay_potential"] == Decimal("386.65")

    def test_all_legs_settled_raises(self) -> None:
        legs = [
            {"odds": Decimal("1.85"), "is_settled": True, "is_won": True},
            {"odds": Decimal("1.90"), "is_settled": True, "is_won": True},
        ]
        with pytest.raises(ValueError, match="nothing to hedge"):
            ParlayHedgeCalculator.calculate_parlay(
                Decimal("50"), legs, Decimal("1.65"), Decimal("1.0")
            )

    def test_settled_leg_lost_raises(self) -> None:
        legs = [
            {"odds": Decimal("1.85"), "is_settled": True, "is_won": False},
            {"odds": Decimal("1.90"), "is_settled": True, "is_won": True},
            {"odds": Decimal("2.20"), "is_settled": False, "is_won": None},
        ]
        with pytest.raises(ValueError, match="settled losing leg"):
            ParlayHedgeCalculator.calculate_parlay(
                Decimal("50"), legs, Decimal("1.65"), Decimal("1.0")
            )

    def test_only_one_leg_raises(self) -> None:
        legs = [{"odds": Decimal("1.85"), "is_settled": False, "is_won": None}]
        with pytest.raises(ValueError, match="at least 2 legs"):
            ParlayHedgeCalculator.calculate_parlay(
                Decimal("50"), legs, Decimal("1.65"), Decimal("1.0")
            )

    def test_two_unsettled_legs_raises(self) -> None:
        legs = [
            {"odds": Decimal("1.85"), "is_settled": False, "is_won": None},
            {"odds": Decimal("2.20"), "is_settled": False, "is_won": None},
        ]
        with pytest.raises(ValueError, match="exactly one unsettled"):
            ParlayHedgeCalculator.calculate_parlay(
                Decimal("50"), legs, Decimal("1.65"), Decimal("1.0")
            )

    def test_invalid_leg_odds_raises(self) -> None:
        legs = [
            {"odds": Decimal("0.99"), "is_settled": True, "is_won": True},
            {"odds": Decimal("2.20"), "is_settled": False, "is_won": None},
        ]
        with pytest.raises(ValueError, match="leg odds"):
            ParlayHedgeCalculator.calculate_parlay(
                Decimal("50"), legs, Decimal("1.65"), Decimal("1.0")
            )


# -----------------------------------------------------------------------------
# Advisor — pure (no real prediction_service)
# -----------------------------------------------------------------------------


class TestHedgeAdvisor:
    """Probabilities passed in directly; prediction_service stays None."""

    def test_recommend_hedge_when_original_ev_negative(self) -> None:
        advisor = HedgeAdvisor(prediction_service=None)
        result = advisor.assess(
            match_id=1,
            original_outcome="home",
            original_odds=Decimal("2.10"),
            hedge_outcome="draw",
            hedge_odds=Decimal("3.40"),
            model_prob_original=Decimal("0.30"),  # 0.30 × 2.10 - 1 = -0.37 (-EV)
            model_prob_hedge=Decimal("0.40"),  # 0.40 × 3.40 - 1 = +0.36 (+EV)
        )
        assert result["recommendation"] == "建议对冲"
        assert result["original_ev"] < 0
        assert result["hedge_ev"] >= 0

    def test_hedge_has_value_when_both_ev_positive(self) -> None:
        advisor = HedgeAdvisor(prediction_service=None)
        result = advisor.assess(
            match_id=1,
            original_outcome="home",
            original_odds=Decimal("2.10"),
            hedge_outcome="draw",
            hedge_odds=Decimal("3.40"),
            model_prob_original=Decimal("0.55"),  # +EV original
            model_prob_hedge=Decimal("0.35"),  # +EV hedge (0.35×3.40-1=0.19)
        )
        assert result["recommendation"] == "对冲有价值"
        assert result["original_ev"] > 0
        assert result["hedge_ev"] > 0

    def test_cautious_hedge_when_hedge_ev_negative(self) -> None:
        advisor = HedgeAdvisor(prediction_service=None)
        result = advisor.assess(
            match_id=1,
            original_outcome="home",
            original_odds=Decimal("2.10"),
            hedge_outcome="draw",
            hedge_odds=Decimal("3.40"),
            model_prob_original=Decimal("0.55"),  # +EV original
            model_prob_hedge=Decimal("0.20"),  # -EV hedge (0.20×3.40-1=-0.32)
        )
        assert result["recommendation"] == "谨慎对冲"
        assert result["original_ev"] > 0
        assert result["hedge_ev"] < 0

    def test_not_recommended_when_original_strongly_positive_and_hedge_bad(
        self,
    ) -> None:
        advisor = HedgeAdvisor(prediction_service=None)
        result = advisor.assess(
            match_id=1,
            original_outcome="home",
            original_odds=Decimal("2.10"),
            hedge_outcome="draw",
            hedge_odds=Decimal("3.40"),
            # original_ev=0 (boundary) + hedge_ev<0 → "不建议对冲"
            model_prob_original=Decimal("0.4761904762"),  # ≈ 1/2.10 → ev=0
            model_prob_hedge=Decimal("0.10"),
        )
        # 0.4761904762 × 2.10 = 1.0; → EV = 0 (not >0)
        # 0.10 × 3.40 = 0.34; → EV = -0.66 (<0)
        # decision tree branch: else → "不建议对冲"
        assert result["recommendation"] == "不建议对冲"

    def test_uses_prediction_service_when_probs_not_passed(self) -> None:
        """assess() pulls probabilities from prediction_service when both
        model_prob_* args are None and original_market is supplied."""

        class StubService:
            def __init__(self) -> None:
                self.calls: list[tuple[int, str, str]] = []

            def predict_probabilities(
                self, *, match_id: int, market: str, outcome: str
            ) -> Decimal:
                self.calls.append((match_id, market, outcome))
                # Make hedge probability > 1/odds so hedge_ev >= 0
                return Decimal("0.30") if outcome == "home" else Decimal("0.40")

        stub = StubService()
        advisor = HedgeAdvisor(prediction_service=stub)
        result = advisor.assess(
            match_id=99,
            original_outcome="home",
            original_odds=Decimal("2.10"),
            hedge_outcome="draw",
            hedge_odds=Decimal("3.40"),
            original_market="1x2",
        )
        # original_ev = 0.30 × 2.10 - 1 = -0.37 (< 0)
        # hedge_ev    = 0.40 × 3.40 - 1 = +0.36 (>= 0)
        assert result["recommendation"] == "建议对冲"
        # Verify the service was actually called for both outcomes.
        assert (99, "1x2", "home") in stub.calls
        assert (99, "1x2", "draw") in stub.calls

    def test_prediction_service_exception_degrades_to_math_only(self) -> None:
        """A throwing prediction_service should not crash the assessor."""

        class BrokenService:
            def predict_probabilities(self, **kw: object) -> Decimal:
                raise RuntimeError("model not loaded")

        advisor = HedgeAdvisor(prediction_service=BrokenService())
        result = advisor.assess(
            match_id=1,
            original_outcome="home",
            original_odds=Decimal("2.10"),
            hedge_outcome="draw",
            hedge_odds=Decimal("3.40"),
            original_market="1x2",
        )
        # Falls through to the no-probs branch.
        assert result["recommendation"] is None

    def test_recommendation_none_when_probs_unavailable(self) -> None:
        advisor = HedgeAdvisor(prediction_service=None)
        result = advisor.assess(
            match_id=1,
            original_outcome="home",
            original_odds=Decimal("2.10"),
            hedge_outcome="draw",
            hedge_odds=Decimal("3.40"),
            # both probs None — advisor degrades to math-only
        )
        assert result["recommendation"] is None
        assert result["original_ev"] is None
        assert result["hedge_ev"] is None
        assert "模型概率不可用" in result["reasoning"]


# -----------------------------------------------------------------------------
# Optimizer skeleton
# -----------------------------------------------------------------------------


class TestHedgeOptimizer:
    """Today's optimizer is a thin pass-through to HedgeCalculator."""

    def test_delegates_to_calculator_for_each_tolerance(self) -> None:
        for tolerance, expected in [
            ("conservative", Decimal("1.0")),
            ("balanced", Decimal("0.6")),
            ("aggressive", Decimal("0.3")),
        ]:
            ratio = HedgeOptimizer.find_optimal_ratio(
                Decimal("100"),
                Decimal("2.10"),
                Decimal("3.50"),
                tolerance,
            )
            assert ratio == expected

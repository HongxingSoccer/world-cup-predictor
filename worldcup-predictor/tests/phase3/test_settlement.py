"""Unit tests for the pure-math settlement helpers."""
from __future__ import annotations

from decimal import Decimal

import pytest

from src.utils.settlement import (
    actual_result_letter,
    compute_streaks,
    evaluate_best_ev,
    is_1x2_hit,
    is_btts_hit,
    is_ou25_hit,
    is_score_hit,
    predicted_1x2,
)


# --- 1x2 ---


def test_actual_result_letter_for_each_outcome():
    assert actual_result_letter(2, 1) == "H"
    assert actual_result_letter(0, 0) == "D"
    assert actual_result_letter(1, 3) == "A"


def test_predicted_1x2_picks_argmax():
    assert predicted_1x2(0.55, 0.25, 0.20) == "H"
    assert predicted_1x2(0.20, 0.55, 0.25) == "D"
    assert predicted_1x2(0.20, 0.30, 0.50) == "A"


def test_is_1x2_hit_matches_argmax_against_actual():
    assert is_1x2_hit(prob_home=0.55, prob_draw=0.25, prob_away=0.20, home_score=2, away_score=1)
    assert not is_1x2_hit(prob_home=0.55, prob_draw=0.25, prob_away=0.20, home_score=0, away_score=2)


# --- score ---


def test_score_hit_when_actual_in_top_scores():
    top = [{"score": "2-1", "prob": 0.10}, {"score": "1-1", "prob": 0.09}]
    assert is_score_hit(top, home_score=2, away_score=1)
    assert not is_score_hit(top, home_score=4, away_score=0)


def test_score_hit_handles_empty_top_list():
    assert not is_score_hit([], home_score=1, away_score=0)


# --- OU 2.5 ---


def test_ou25_hit_when_prediction_says_over_and_total_over():
    probs = {"2.5": {"over": 0.60, "under": 0.40}}
    # 2 + 1 = 3 → over 2.5 → predicted_over=True, actual=True → hit.
    assert is_ou25_hit(probs, home_score=2, away_score=1) is True
    # 1 + 1 = 2 → under 2.5 → predicted_over=True, actual=False → miss.
    assert is_ou25_hit(probs, home_score=1, away_score=1) is False


def test_ou25_returns_none_when_market_missing():
    assert is_ou25_hit({}, home_score=1, away_score=2) is None
    assert is_ou25_hit({"3.5": {"over": 0.5, "under": 0.5}}, home_score=2, away_score=2) is None


# --- BTTS ---


def test_btts_hit_when_prediction_says_yes_and_both_score():
    assert is_btts_hit(0.65, home_score=2, away_score=1) is True
    assert is_btts_hit(0.65, home_score=2, away_score=0) is False


def test_btts_hit_when_prediction_says_no_and_one_clean_sheet():
    assert is_btts_hit(0.30, home_score=3, away_score=0) is True


def test_btts_returns_none_when_prob_missing():
    assert is_btts_hit(None, home_score=2, away_score=1) is None


# --- best EV / PnL ---


def test_evaluate_best_ev_winning_bet_returns_odds_minus_one():
    hit, pnl = evaluate_best_ev(
        market_type="1x2",
        outcome="home",
        odds=Decimal("2.10"),
        signal_level=2,
        home_score=2,
        away_score=1,
    )
    assert hit is True
    assert pnl == Decimal("1.1000")


def test_evaluate_best_ev_losing_bet_returns_minus_one():
    hit, pnl = evaluate_best_ev(
        market_type="1x2",
        outcome="home",
        odds=Decimal("2.10"),
        signal_level=2,
        home_score=0,
        away_score=2,
    )
    assert hit is False
    assert pnl == Decimal("-1.0000")


def test_evaluate_best_ev_no_signal_returns_zero():
    hit, pnl = evaluate_best_ev(
        market_type="1x2",
        outcome="home",
        odds=Decimal("2.10"),
        signal_level=0,
        home_score=1,
        away_score=0,
    )
    assert hit is None
    assert pnl == Decimal("0")


def test_evaluate_best_ev_handles_btts_and_ou_markets():
    hit_btts, _ = evaluate_best_ev(
        market_type="btts", outcome="yes", odds=Decimal("1.90"),
        signal_level=1, home_score=2, away_score=1,
    )
    assert hit_btts is True

    hit_under, pnl_under = evaluate_best_ev(
        market_type="over_under", outcome="under", odds=Decimal("1.90"),
        signal_level=1, home_score=1, away_score=1,
    )
    assert hit_under is True
    assert pnl_under == Decimal("0.9000")


# --- streaks ---


def test_compute_streaks_handles_winning_run():
    assert compute_streaks([True, True, True]) == (3, 3)


def test_compute_streaks_handles_losing_run():
    assert compute_streaks([False, False, False]) == (-3, 0)


def test_compute_streaks_resets_on_alternation():
    # Last result is a win → current_streak = +1; best winning run was 3.
    assert compute_streaks([True, True, True, False, True]) == (1, 3)


def test_compute_streaks_signed_after_loss():
    # Two wins, then a loss → current_streak = -1.
    assert compute_streaks([True, True, False]) == (-1, 2)


def test_compute_streaks_empty_input():
    assert compute_streaks([]) == (0, 0)


@pytest.mark.parametrize(
    "hits,expected_current,expected_best",
    [
        ([True], 1, 1),
        ([False], -1, 0),
        ([True, False, True, True], 2, 2),
        ([False, False, True], 1, 1),
    ],
)
def test_compute_streaks_parametrised(hits, expected_current, expected_best):
    assert compute_streaks(hits) == (expected_current, expected_best)

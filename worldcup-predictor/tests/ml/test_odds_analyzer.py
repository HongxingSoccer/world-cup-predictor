"""Unit tests for `OddsAnalyzer` + the pure-math helpers it composes."""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest

from src.ml.models.base import PredictionResult
from src.ml.odds.analyzer import OddsAnalyzer
from src.ml.odds.ev_calculator import compute_edge, compute_ev, signal_level
from src.ml.odds.vig_removal import remove_vig
from src.models.odds_snapshot import OddsSnapshot

# --- Pure-math tests -------------------------------------------------------


def test_remove_vig_returns_probabilities_summing_to_one():
    fair = remove_vig({"home": 2.10, "draw": 3.40, "away": 3.30})
    assert sum(fair.values()) == pytest.approx(1.0)
    # Bookmaker basket has Σ(1/odds) ≈ 1.07 → margin ≈ 7%; fair home ≈ 0.475 / 1.07
    assert 0.40 < fair["home"] < 0.50


def test_remove_vig_rejects_zero_or_negative_odds():
    with pytest.raises(ValueError):
        remove_vig({"home": 0.0, "away": 2.0})


def test_doc_example_ev_and_edge_match_spec():
    # Spec: model_prob 0.55 vs odds 2.10 → implied 0.476, EV 0.155, edge 0.074.
    implied = 1 / 2.10
    ev = compute_ev(0.55, 2.10)
    edge = compute_edge(0.55, implied)
    assert implied == pytest.approx(0.476, abs=1e-3)
    assert ev == pytest.approx(0.155, abs=1e-3)
    assert edge == pytest.approx(0.074, abs=1e-3)


def test_signal_level_thresholds_per_spec():
    # Strict-greater thresholds: boundary values do NOT promote.
    assert signal_level(0.16, 0.09) == 3
    # 3 needs both > thresholds; falling on either side drops to 2.
    assert signal_level(0.155, 0.074) == 2  # the doc example with strict thresholds
    assert signal_level(0.10, 0.06) == 2
    assert signal_level(0.06, 0.04) == 1
    assert signal_level(0.04, 0.10) == 0  # EV too small
    assert signal_level(-0.10, 0.05) == 0  # negative EV


def test_compute_ev_rejects_invalid_inputs():
    with pytest.raises(ValueError):
        compute_ev(1.5, 2.0)
    with pytest.raises(ValueError):
        compute_ev(0.5, 1.0)


# --- Analyzer integration (uses SQLite-backed odds_snapshots) -------------


def test_analyze_match_picks_best_bookmaker_per_outcome(
    db_session, make_match, utc, seed_world
):
    target = make_match(utc(2026, 5, 1, 18))
    pre_kickoff = target.match_date - timedelta(hours=2)

    # Two bookmakers; pinnacle is sharpest on home, draftkings on away.
    db_session.add_all(
        [
            OddsSnapshot(
                match_id=target.id,
                bookmaker="pinnacle",
                market_type="1x2",
                outcome_home=Decimal("2.20"),
                outcome_draw=Decimal("3.30"),
                outcome_away=Decimal("3.10"),
                snapshot_at=pre_kickoff,
                data_source="test",
            ),
            OddsSnapshot(
                match_id=target.id,
                bookmaker="draftkings",
                market_type="1x2",
                outcome_home=Decimal("2.10"),
                outcome_draw=Decimal("3.20"),
                outcome_away=Decimal("3.40"),
                snapshot_at=pre_kickoff,
                data_source="test",
            ),
        ]
    )
    db_session.flush()

    prediction = _stub_prediction(home=0.55, draw=0.25, away=0.20)
    analyzer = OddsAnalyzer(db_session)
    results = analyzer.analyze_match(target.id, prediction)

    by_outcome = {r.outcome: r for r in results if r.market_type == "1x2"}
    assert by_outcome["home"].best_bookmaker == "pinnacle"  # 2.20 > 2.10
    assert by_outcome["away"].best_bookmaker == "draftkings"  # 3.40 > 3.10


def test_analyze_match_skips_markets_with_no_snapshots(
    db_session, make_match, utc, seed_world
):
    target = make_match(utc(2026, 5, 1, 18))
    db_session.flush()

    prediction = _stub_prediction(home=0.50, draw=0.30, away=0.20)
    results = OddsAnalyzer(db_session).analyze_match(target.id, prediction)
    assert results == []


def test_analyze_match_excludes_post_kickoff_snapshots(
    db_session, make_match, utc, seed_world
):
    target = make_match(utc(2026, 5, 1, 18))
    post_kickoff = target.match_date + timedelta(minutes=30)

    db_session.add(
        OddsSnapshot(
            match_id=target.id,
            bookmaker="pinnacle",
            market_type="1x2",
            outcome_home=Decimal("2.10"),
            outcome_draw=Decimal("3.20"),
            outcome_away=Decimal("3.40"),
            snapshot_at=post_kickoff,
            data_source="test",
        )
    )
    db_session.flush()

    prediction = _stub_prediction(home=0.55, draw=0.25, away=0.20)
    results = OddsAnalyzer(db_session).analyze_match(target.id, prediction)
    assert results == []  # Only post-kickoff snapshot exists; analyzer ignores it.


def test_analyze_match_ranks_by_signal_then_ev(
    db_session, make_match, utc, seed_world
):
    target = make_match(utc(2026, 5, 1, 18))
    pre = target.match_date - timedelta(hours=2)

    db_session.add(
        OddsSnapshot(
            match_id=target.id,
            bookmaker="pinnacle",
            market_type="1x2",
            outcome_home=Decimal("3.20"),
            outcome_draw=Decimal("3.40"),
            outcome_away=Decimal("2.30"),
            snapshot_at=pre,
            data_source="test",
        )
    )
    db_session.flush()

    # Strong model conviction on draw → only "draw" should score a signal_level.
    prediction = _stub_prediction(home=0.20, draw=0.60, away=0.20)
    results = OddsAnalyzer(db_session).analyze_match(target.id, prediction)

    levels = [r.signal_level for r in results if r.market_type == "1x2"]
    # Sort invariant: any level-3 entries appear before level-0 entries.
    assert levels == sorted(levels, reverse=True)


def _stub_prediction(*, home: float, draw: float, away: float) -> PredictionResult:
    return PredictionResult(
        prob_home_win=home,
        prob_draw=draw,
        prob_away_win=away,
        lambda_home=1.5,
        lambda_away=1.0,
        score_matrix=[[0.0] * 10 for _ in range(10)],
        top_scores=[],
        over_under_probs={"2.5": {"over": 0.55, "under": 0.45}},
        btts_prob=0.50,
    )

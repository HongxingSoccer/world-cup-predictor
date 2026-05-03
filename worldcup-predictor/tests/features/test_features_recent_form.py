"""Unit tests for `RecentFormFeatures`."""
from __future__ import annotations

import pytest

from src.ml.features.recent_form import RecentFormFeatures


def test_compute_no_history_returns_zero_baseline(
    db_session, make_match, utc
):
    match = make_match(utc(2026, 5, 1))

    result = RecentFormFeatures(db_session).compute(match.id, match.match_date)

    assert result["home_win_rate_last5"] == 0.0
    assert result["away_win_rate_last5"] == 0.0
    assert result["home_goals_scored_avg5"] == 0.0
    assert result["away_goals_scored_avg5"] == 0.0
    assert result["home_unbeaten_streak"] == 0
    assert result["away_unbeaten_streak"] == 0


def test_compute_aggregates_last_five_finished_matches(
    db_session, make_match, utc, seed_world
):
    home = seed_world["home_team_id"]
    away = seed_world["away_team_id"]
    # 5 prior finished matches, all home wins, alternating venues.
    for i in range(5):
        make_match(
            utc(2026, 4, 25 - i),
            home_score=3,
            away_score=1,
            home_team_id=home,
            away_team_id=away,
        )
    db_session.flush()

    target = make_match(utc(2026, 5, 1))
    result = RecentFormFeatures(db_session).compute(target.id, target.match_date)

    assert result["home_win_rate_last5"] == pytest.approx(1.0)
    assert result["away_win_rate_last5"] == pytest.approx(0.0)
    assert result["home_goals_scored_avg5"] == pytest.approx(3.0)
    assert result["home_goals_conceded_avg5"] == pytest.approx(1.0)
    # Unbeaten streak hits 5 (no losses in window) but cap is 20.
    assert result["home_unbeaten_streak"] == 5


def test_compute_data_leakage_protection_excludes_future_matches(
    db_session, make_match, utc, seed_world
):
    home = seed_world["home_team_id"]
    away = seed_world["away_team_id"]
    # One finished match before cutoff.
    make_match(
        utc(2026, 4, 1),
        home_score=2, away_score=1,
        home_team_id=home, away_team_id=away,
    )
    # One *after* cutoff — must not be included.
    make_match(
        utc(2026, 6, 1),
        home_score=0, away_score=5,
        home_team_id=home, away_team_id=away,
    )
    db_session.flush()
    target = make_match(utc(2026, 5, 1))

    result = RecentFormFeatures(db_session).compute(target.id, target.match_date)

    # If the future match leaked, win_rate would be 0.5 and goals_avg = 2 (not 1.0/2.0).
    assert result["home_win_rate_last5"] == pytest.approx(1.0)
    assert result["home_goals_scored_avg5"] == pytest.approx(2.0)


def test_unbeaten_streak_breaks_on_first_loss(
    db_session, make_match, utc, seed_world
):
    home = seed_world["home_team_id"]
    away = seed_world["away_team_id"]
    # Most recent → loss; streak = 0.
    make_match(utc(2026, 4, 30), home_score=0, away_score=2,
               home_team_id=home, away_team_id=away)
    # Older → win; doesn't matter, streak stops on loss.
    make_match(utc(2026, 4, 15), home_score=3, away_score=1,
               home_team_id=home, away_team_id=away)
    db_session.flush()

    target = make_match(utc(2026, 5, 1))
    result = RecentFormFeatures(db_session).compute(target.id, target.match_date)

    assert result["home_unbeaten_streak"] == 0


def test_get_feature_names_has_eight_entries(db_session):
    assert len(RecentFormFeatures(db_session).get_feature_names()) == 8

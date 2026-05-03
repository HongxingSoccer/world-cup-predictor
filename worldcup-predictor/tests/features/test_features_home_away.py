"""Unit tests for `HomeAwayFeatures`."""
from __future__ import annotations

import pytest

from src.ml.features.home_away import HomeAwayFeatures


def test_compute_no_history_returns_zero(db_session, make_match, utc):
    match = make_match(utc(2026, 5, 1))
    result = HomeAwayFeatures(db_session).compute(match.id, match.match_date)
    assert result == {
        "home_home_win_rate": 0.0,
        "away_away_win_rate": 0.0,
        "home_home_goals_avg": 0.0,
        "away_away_goals_avg": 0.0,
    }


def test_compute_uses_only_same_season_matches(
    db_session, make_match, utc, seed_world
):
    home = seed_world["home_team_id"]
    away = seed_world["away_team_id"]
    # Same season home games for `home`.
    for i in range(3):
        make_match(
            utc(2026, 4, 25 - i),
            home_score=3,
            away_score=1,
            home_team_id=home,
            away_team_id=away,
        )
    db_session.flush()

    target = make_match(utc(2026, 5, 1))
    result = HomeAwayFeatures(db_session).compute(target.id, target.match_date)
    assert result["home_home_win_rate"] == pytest.approx(1.0)
    assert result["home_home_goals_avg"] == pytest.approx(3.0)


def test_compute_data_leakage_protection_excludes_future(
    db_session, make_match, utc, seed_world
):
    home = seed_world["home_team_id"]
    away = seed_world["away_team_id"]
    # Past home game: 1-0 win.
    make_match(utc(2026, 4, 1), home_score=1, away_score=0,
               home_team_id=home, away_team_id=away)
    # Future home game: must not affect features.
    make_match(utc(2026, 6, 1), home_score=0, away_score=5,
               home_team_id=home, away_team_id=away)
    db_session.flush()

    target = make_match(utc(2026, 5, 1))
    result = HomeAwayFeatures(db_session).compute(target.id, target.match_date)
    assert result["home_home_win_rate"] == pytest.approx(1.0)
    assert result["home_home_goals_avg"] == pytest.approx(1.0)


def test_compute_isolates_away_team_road_record(
    db_session, make_match, utc, seed_world
):
    home = seed_world["home_team_id"]
    away = seed_world["away_team_id"]
    # `away` plays as visitor at `home` and wins twice (away_score > home_score).
    make_match(utc(2026, 4, 1), home_score=0, away_score=2,
               home_team_id=home, away_team_id=away)
    make_match(utc(2026, 4, 15), home_score=1, away_score=2,
               home_team_id=home, away_team_id=away)
    db_session.flush()

    target = make_match(utc(2026, 5, 1))
    result = HomeAwayFeatures(db_session).compute(target.id, target.match_date)
    assert result["away_away_win_rate"] == pytest.approx(1.0)
    assert result["away_away_goals_avg"] == pytest.approx(2.0)


def test_get_feature_names_has_four_entries(db_session):
    assert len(HomeAwayFeatures(db_session).get_feature_names()) == 4

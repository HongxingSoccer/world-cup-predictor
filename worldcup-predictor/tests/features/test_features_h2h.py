"""Unit tests for `H2HFeatures`."""
from __future__ import annotations

import pytest

from src.ml.features.h2h import H2H_TOTAL_CAP, H2HFeatures


def test_compute_no_history_returns_zero(db_session, make_match, utc):
    match = make_match(utc(2026, 5, 1))
    result = H2HFeatures(db_session).compute(match.id, match.match_date)
    assert result == {
        "h2h_home_win_rate": 0.0,
        "h2h_total_matches": 0,
        "h2h_avg_goals": 0.0,
    }


def test_compute_aggregates_past_meetings_at_either_venue(
    db_session, make_match, utc, seed_world
):
    home = seed_world["home_team_id"]
    away = seed_world["away_team_id"]
    # 4 past meetings: 2 home wins, 1 draw, 1 away win.
    make_match(utc(2026, 1, 1), home_score=2, away_score=1, home_team_id=home, away_team_id=away)
    make_match(utc(2026, 2, 1), home_score=3, away_score=2, home_team_id=home, away_team_id=away)
    make_match(utc(2026, 3, 1), home_score=1, away_score=1, home_team_id=home, away_team_id=away)
    # Reverse-fixture: `home` plays as visitor and loses.
    make_match(utc(2026, 4, 1), home_score=2, away_score=0, home_team_id=away, away_team_id=home)
    db_session.flush()

    target = make_match(utc(2026, 5, 1))
    result = H2HFeatures(db_session).compute(target.id, target.match_date)

    # `home` won 2 of 4.
    assert result["h2h_home_win_rate"] == pytest.approx(0.5)
    assert result["h2h_total_matches"] == 4
    # Total goals = (3 + 5 + 2 + 2) = 12 → avg = 3.0
    assert result["h2h_avg_goals"] == pytest.approx(3.0)


def test_compute_data_leakage_protection_excludes_future_meetings(
    db_session, make_match, utc, seed_world
):
    home = seed_world["home_team_id"]
    away = seed_world["away_team_id"]
    make_match(utc(2026, 4, 1), home_score=1, away_score=0,
               home_team_id=home, away_team_id=away)
    # Future meeting — must not be counted.
    make_match(utc(2026, 6, 1), home_score=0, away_score=5,
               home_team_id=home, away_team_id=away)
    db_session.flush()

    target = make_match(utc(2026, 5, 1))
    result = H2HFeatures(db_session).compute(target.id, target.match_date)
    assert result["h2h_total_matches"] == 1
    assert result["h2h_home_win_rate"] == pytest.approx(1.0)


def test_total_matches_is_capped(
    db_session, make_match, utc, seed_world
):
    home = seed_world["home_team_id"]
    away = seed_world["away_team_id"]
    cap_plus = H2H_TOTAL_CAP + 5
    for i in range(cap_plus):
        make_match(
            utc(2025, 1, 1 + (i % 28) ),
            home_score=1, away_score=1,
            home_team_id=home, away_team_id=away,
        )
    db_session.flush()

    target = make_match(utc(2026, 5, 1))
    result = H2HFeatures(db_session).compute(target.id, target.match_date)
    assert result["h2h_total_matches"] == H2H_TOTAL_CAP


def test_get_feature_names_has_three_entries(db_session):
    assert len(H2HFeatures(db_session).get_feature_names()) == 3

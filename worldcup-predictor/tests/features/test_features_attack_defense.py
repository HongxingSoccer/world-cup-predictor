"""Unit tests for `AttackDefenseFeatures`."""
from __future__ import annotations

from decimal import Decimal

import pytest

from src.ml.features.attack_defense import AttackDefenseFeatures
from src.models.match_stats import MatchStats


def test_compute_no_stats_returns_zero(db_session, make_match, utc):
    match = make_match(utc(2026, 5, 1))
    result = AttackDefenseFeatures(db_session).compute(match.id, match.match_date)
    assert result["home_xg_avg5"] == 0.0
    assert result["home_xg_against_avg5"] == 0.0
    assert result["home_shot_accuracy_avg5"] == 0.0


def test_compute_averages_xg_across_recent_matches(
    db_session, make_match, utc, seed_world
):
    home = seed_world["home_team_id"]
    away = seed_world["away_team_id"]
    # Three past matches with xG=1.0, 2.0, 3.0 → avg = 2.0
    for i, xg in enumerate((Decimal("1.0"), Decimal("2.0"), Decimal("3.0"))):
        match = make_match(
            utc(2026, 4, 25 - i),
            home_score=2,
            away_score=1,
            home_team_id=home,
            away_team_id=away,
        )
        db_session.add(
            MatchStats(
                match_id=match.id,
                team_id=home,
                is_home=True,
                xg=xg,
                xg_against=Decimal("1.0"),
                shots=10,
                shots_on_target=5,
                data_source="test",
            )
        )
    db_session.flush()
    target = make_match(utc(2026, 5, 1))

    result = AttackDefenseFeatures(db_session).compute(target.id, target.match_date)
    assert result["home_xg_avg5"] == pytest.approx(2.0)
    assert result["home_xg_against_avg5"] == pytest.approx(1.0)
    assert result["home_shot_accuracy_avg5"] == pytest.approx(0.5)


def test_xg_falls_back_to_actual_goals_when_missing(
    db_session, make_match, utc, seed_world
):
    home = seed_world["home_team_id"]
    away = seed_world["away_team_id"]
    match = make_match(
        utc(2026, 4, 1),
        home_score=4,
        away_score=0,
        home_team_id=home,
        away_team_id=away,
    )
    db_session.add(
        MatchStats(
            match_id=match.id,
            team_id=home,
            is_home=True,
            xg=None,  # provider didn't ship xG
            xg_against=None,
            shots=20,
            shots_on_target=10,
            data_source="test",
        )
    )
    db_session.flush()
    target = make_match(utc(2026, 5, 1))

    result = AttackDefenseFeatures(db_session).compute(target.id, target.match_date)
    # Fallback uses the team's actual goals scored.
    assert result["home_xg_avg5"] == pytest.approx(4.0)
    # xg_against fallback uses opponent's score.
    assert result["home_xg_against_avg5"] == pytest.approx(0.0)


def test_compute_data_leakage_protection_excludes_future_stats(
    db_session, make_match, utc, seed_world
):
    home = seed_world["home_team_id"]
    away = seed_world["away_team_id"]
    # Past match with low xG.
    past = make_match(utc(2026, 4, 1), home_score=1, away_score=1,
                      home_team_id=home, away_team_id=away)
    db_session.add(MatchStats(match_id=past.id, team_id=home, is_home=True,
                              xg=Decimal("0.5"), shots=10, shots_on_target=3, data_source="test"))
    # Future match with huge xG — must not leak.
    future = make_match(utc(2026, 6, 1), home_score=5, away_score=0,
                        home_team_id=home, away_team_id=away)
    db_session.add(MatchStats(match_id=future.id, team_id=home, is_home=True,
                              xg=Decimal("9.9"), shots=30, shots_on_target=20, data_source="test"))
    db_session.flush()

    target = make_match(utc(2026, 5, 1))
    result = AttackDefenseFeatures(db_session).compute(target.id, target.match_date)

    assert result["home_xg_avg5"] == pytest.approx(0.5)


def test_get_feature_names_has_six_entries(db_session):
    assert len(AttackDefenseFeatures(db_session).get_feature_names()) == 6

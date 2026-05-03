"""Unit tests for `EloFeatures`."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from src.ml.features.elo import EloFeatures
from src.models.elo_rating import EloRating
from src.utils.elo import INITIAL_RATING, expected_score


def test_compute_no_history_falls_back_to_initial_rating(
    db_session, make_match, utc, seed_world
):
    match = make_match(utc(2026, 5, 1))

    result = EloFeatures(db_session).compute(match.id, match.match_date)

    assert result["home_elo"] == INITIAL_RATING
    assert result["away_elo"] == INITIAL_RATING
    assert result["elo_diff"] == 0
    assert result["elo_win_prob"] == pytest.approx(0.5)


def test_compute_picks_latest_rating_strictly_before_cutoff(
    db_session, make_match, utc, seed_world
):
    home = seed_world["home_team_id"]
    away = seed_world["away_team_id"]
    db_session.add_all(
        [
            EloRating(team_id=home, rating=Decimal("1600.00"), rated_at=date(2026, 4, 1)),
            EloRating(team_id=home, rating=Decimal("1700.00"), rated_at=date(2026, 4, 15)),
            EloRating(team_id=away, rating=Decimal("1500.00"), rated_at=date(2026, 4, 10)),
        ]
    )
    match = make_match(utc(2026, 5, 1))
    db_session.flush()

    result = EloFeatures(db_session).compute(match.id, match.match_date)

    assert result["home_elo"] == 1700.0
    assert result["away_elo"] == 1500.0
    assert result["elo_diff"] == 200.0
    assert result["elo_win_prob"] == pytest.approx(expected_score(1700.0, 1500.0))


def test_compute_excludes_future_dated_ratings_from_leakage(
    db_session, make_match, utc, seed_world
):
    home = seed_world["home_team_id"]
    db_session.add_all(
        [
            EloRating(team_id=home, rating=Decimal("1600.00"), rated_at=date(2026, 1, 1)),
            # Future rating relative to cutoff — must NOT influence the feature.
            EloRating(team_id=home, rating=Decimal("9999.00"), rated_at=date(2026, 12, 31)),
        ]
    )
    match = make_match(utc(2026, 5, 1))
    db_session.flush()

    result = EloFeatures(db_session).compute(match.id, match.match_date)
    assert result["home_elo"] == 1600.0


def test_get_feature_names_returns_expected_set(db_session):
    names = EloFeatures(db_session).get_feature_names()
    assert names == ["home_elo", "away_elo", "elo_diff", "elo_win_prob"]

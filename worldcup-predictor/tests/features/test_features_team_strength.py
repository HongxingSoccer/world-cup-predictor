"""Unit tests for `TeamStrengthFeatures`."""
from __future__ import annotations

import math
from datetime import date

import pytest

from src.ml.features.team_strength import TeamStrengthFeatures
from src.models.player import Player
from src.models.player_valuation import PlayerValuation


def test_compute_no_squad_returns_zero(db_session, make_match, utc):
    match = make_match(utc(2026, 5, 1))
    result = TeamStrengthFeatures(db_session).compute(match.id, match.match_date)
    assert result["home_squad_value_log"] == 0.0
    assert result["away_squad_value_log"] == 0.0
    assert result["value_ratio"] == 0.0


def test_compute_sums_latest_pre_cutoff_valuations(
    db_session, make_match, utc, seed_world
):
    home = seed_world["home_team_id"]
    away = seed_world["away_team_id"]
    # Home roster: 2 players worth a total of 100M.
    p1 = Player(name="P1", current_team_id=home)
    p2 = Player(name="P2", current_team_id=home)
    p_away = Player(name="A1", current_team_id=away)
    db_session.add_all([p1, p2, p_away])
    db_session.flush()

    # Older valuation, then newer (must use newer).
    db_session.add_all([
        PlayerValuation(player_id=p1.id, value_date=date(2026, 1, 1),
                        market_value_eur=10_000_000),
        PlayerValuation(player_id=p1.id, value_date=date(2026, 4, 1),
                        market_value_eur=60_000_000),
        PlayerValuation(player_id=p2.id, value_date=date(2026, 4, 1),
                        market_value_eur=40_000_000),
        PlayerValuation(player_id=p_away.id, value_date=date(2026, 4, 1),
                        market_value_eur=10_000_000),
    ])
    db_session.flush()

    target = make_match(utc(2026, 5, 1))
    result = TeamStrengthFeatures(db_session).compute(target.id, target.match_date)

    assert result["home_squad_value_log"] == pytest.approx(math.log10(100_000_001))
    assert result["away_squad_value_log"] == pytest.approx(math.log10(10_000_001))
    assert result["value_ratio"] == pytest.approx(math.log(100_000_000 / 10_000_000))


def test_compute_data_leakage_protection_excludes_future_valuations(
    db_session, make_match, utc, seed_world
):
    home = seed_world["home_team_id"]
    p1 = Player(name="P", current_team_id=home)
    db_session.add(p1)
    db_session.flush()
    # Past valuation.
    db_session.add(PlayerValuation(player_id=p1.id, value_date=date(2026, 1, 1),
                                    market_value_eur=20_000_000))
    # Future valuation (huge) — must not leak.
    db_session.add(PlayerValuation(player_id=p1.id, value_date=date(2026, 12, 1),
                                    market_value_eur=999_999_999))
    db_session.flush()

    target = make_match(utc(2026, 5, 1))
    result = TeamStrengthFeatures(db_session).compute(target.id, target.match_date)

    assert result["home_squad_value_log"] == pytest.approx(math.log10(20_000_001))


def test_value_ratio_safe_when_one_side_zero(
    db_session, make_match, utc, seed_world
):
    home = seed_world["home_team_id"]
    p = Player(name="X", current_team_id=home)
    db_session.add(p)
    db_session.flush()
    db_session.add(PlayerValuation(player_id=p.id, value_date=date(2026, 1, 1),
                                    market_value_eur=50_000_000))
    db_session.flush()

    target = make_match(utc(2026, 5, 1))
    result = TeamStrengthFeatures(db_session).compute(target.id, target.match_date)
    # Away has no players → away_value=0 → safe ratio = 0.
    assert result["value_ratio"] == 0.0


def test_get_feature_names_has_three_entries(db_session):
    assert len(TeamStrengthFeatures(db_session).get_feature_names()) == 3

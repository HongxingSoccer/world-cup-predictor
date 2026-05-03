"""Unit tests for src.ml.simulation.monte_carlo."""
from __future__ import annotations

import numpy as np
import pytest

from src.ml.simulation.monte_carlo import (
    GroupFixture,
    KnockoutMatch,
    simulate_group_stage,
    simulate_knockout_bracket,
    simulate_match,
)


def _matrix_favouring_home() -> list[list[float]]:
    """10×10 matrix with most mass in the 2-0/3-0/2-1 cells."""
    matrix = np.full((10, 10), 1e-6)
    matrix[2, 0] = 0.4
    matrix[3, 0] = 0.3
    matrix[2, 1] = 0.2
    matrix[1, 1] = 0.1
    matrix = matrix / matrix.sum()
    return matrix.tolist()


def _matrix_favouring_away() -> list[list[float]]:
    matrix = np.full((10, 10), 1e-6)
    matrix[0, 2] = 0.4
    matrix[0, 3] = 0.3
    matrix[1, 2] = 0.2
    matrix[1, 1] = 0.1
    matrix = matrix / matrix.sum()
    return matrix.tolist()


def test_simulate_match_returns_valid_indices():
    rng = np.random.default_rng(0)
    h, a = simulate_match(_matrix_favouring_home(), rng)
    assert 0 <= h < 10 and 0 <= a < 10


def test_group_simulation_promotes_strong_team_to_first():
    fixtures = [
        GroupFixture("A", "B", _matrix_favouring_home()),  # A beats B
        GroupFixture("A", "C", _matrix_favouring_home()),  # A beats C
        GroupFixture("B", "C", _matrix_favouring_home()),  # B beats C
    ]
    standings = simulate_group_stage(fixtures, trials=500, seed=123)
    by_team = {s.team: s for s in standings}
    assert by_team["A"].qualify_first_prob > 0.7
    assert by_team["C"].qualify_prob < by_team["A"].qualify_prob


def test_knockout_bracket_returns_probs_summing_to_match_count():
    bracket = [
        KnockoutMatch("X", "Y", _matrix_favouring_home()),
        KnockoutMatch("Z", "W", _matrix_favouring_away()),
    ]
    probs = simulate_knockout_bracket(bracket, trials=500, seed=1)
    total = sum(probs.values())
    assert total == pytest.approx(2.0, abs=1e-6)


def test_empty_fixtures_return_empty_standings():
    assert simulate_group_stage([], trials=10) == []


def test_simulation_is_deterministic_with_seed():
    fixtures = [GroupFixture("A", "B", _matrix_favouring_home())]
    a = simulate_group_stage(fixtures, trials=200, seed=42)
    b = simulate_group_stage(fixtures, trials=200, seed=42)
    assert a == b

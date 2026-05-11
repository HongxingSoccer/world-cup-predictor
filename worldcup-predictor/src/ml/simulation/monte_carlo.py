"""Monte Carlo tournament simulator (Phase 4 v1).

Given a per-match score-probability matrix (10×10, ``[i][j] = P(home=i, away=j)``)
the simulator can:

* :func:`simulate_match` — draw a single concrete scoreline.
* :func:`simulate_group_stage` — play out a list of group fixtures
  ``trials`` times each, accumulating expected points / goal-difference and
  computing first/second-place qualification probabilities.
* :func:`simulate_knockout_bracket` — sequentially resolve a single-elim
  bracket of arbitrary depth, returning championship probability per team.

The functions are pure NumPy / RNG — no DB or model coupling — so they can
be unit-tested in isolation. Higher-level code feeds them probabilities
produced by any :class:`BasePredictionModel`.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

import numpy as np

DEFAULT_TRIALS: int = 10_000
WIN_POINTS: int = 3
DRAW_POINTS: int = 1


@dataclass(frozen=True)
class GroupFixture:
    """One round-robin fixture and its score-probability matrix."""

    home_team: str
    away_team: str
    score_matrix: list[list[float]]


@dataclass
class TeamStanding:
    """Aggregated per-team results across all simulated trials."""

    team: str
    expected_points: float = 0.0
    expected_gd: float = 0.0
    qualify_first_prob: float = 0.0
    qualify_second_prob: float = 0.0
    qualify_prob: float = 0.0


@dataclass(frozen=True)
class KnockoutMatch:
    """One knockout fixture; ``score_matrix`` resolves draws via penalties."""

    team_a: str
    team_b: str
    score_matrix: list[list[float]]


@dataclass
class TournamentResult:
    """Output of :func:`simulate_group_stage` + bracket runs."""

    standings: list[TeamStanding] = field(default_factory=list)
    champion_prob: dict[str, float] = field(default_factory=dict)
    trials: int = 0


def simulate_match(
    score_matrix: list[list[float]], rng: np.random.Generator
) -> tuple[int, int]:
    """Draw one (home_goals, away_goals) sample from the matrix."""
    arr = np.asarray(score_matrix, dtype=float)
    flat = arr.flatten()
    total = float(flat.sum())
    if total <= 0:
        return 0, 0
    flat = flat / total
    n = arr.shape[0]
    idx = int(rng.choice(flat.size, p=flat))
    return divmod(idx, n)


def simulate_group_stage(
    fixtures: list[GroupFixture],
    *,
    trials: int = DEFAULT_TRIALS,
    qualifiers_per_group: int = 2,
    seed: int | None = None,
) -> list[TeamStanding]:
    """Run ``trials`` Monte Carlo plays of one group; return team standings."""
    if not fixtures:
        return []
    rng = np.random.default_rng(seed)
    teams = sorted({t for f in fixtures for t in (f.home_team, f.away_team)})
    points = {t: 0.0 for t in teams}
    gd = {t: 0.0 for t in teams}
    first_count = {t: 0 for t in teams}
    second_count = {t: 0 for t in teams}

    for _ in range(trials):
        trial_pts: dict[str, int] = defaultdict(int)
        trial_gd: dict[str, int] = defaultdict(int)
        for fixture in fixtures:
            h, a = simulate_match(fixture.score_matrix, rng)
            _apply_match_result(fixture, h, a, trial_pts, trial_gd)
        ranked = _rank_group(teams, trial_pts, trial_gd)
        for rank, team in enumerate(ranked):
            if rank == 0:
                first_count[team] += 1
            elif rank == 1 and qualifiers_per_group >= 2:
                second_count[team] += 1
        for t in teams:
            points[t] += trial_pts[t]
            gd[t] += trial_gd[t]

    return _build_standings(teams, points, gd, first_count, second_count, trials)


def simulate_knockout_bracket(
    bracket: list[KnockoutMatch],
    *,
    trials: int = DEFAULT_TRIALS,
    seed: int | None = None,
) -> dict[str, float]:
    """Resolve a single-round knockout list ``trials`` times.

    For brackets with multiple rounds, callers chain calls and pass the
    winners forward — keeping this primitive small and testable.
    """
    rng = np.random.default_rng(seed)
    win_count: dict[str, int] = defaultdict(int)
    for _ in range(trials):
        for match in bracket:
            winner = _knockout_winner(match, rng)
            win_count[winner] += 1
    return {team: count / trials for team, count in win_count.items()}


# --- Internal helpers -------------------------------------------------------


def _apply_match_result(
    fixture: GroupFixture,
    home_goals: int,
    away_goals: int,
    points: dict[str, int],
    gd: dict[str, int],
) -> None:
    gd[fixture.home_team] += home_goals - away_goals
    gd[fixture.away_team] += away_goals - home_goals
    if home_goals > away_goals:
        points[fixture.home_team] += WIN_POINTS
    elif away_goals > home_goals:
        points[fixture.away_team] += WIN_POINTS
    else:
        points[fixture.home_team] += DRAW_POINTS
        points[fixture.away_team] += DRAW_POINTS


def _rank_group(
    teams: list[str], points: dict[str, int], gd: dict[str, int]
) -> list[str]:
    """Sort teams by (points desc, gd desc, team asc) — deterministic tiebreak."""
    return sorted(teams, key=lambda t: (-points[t], -gd[t], t))


def _build_standings(
    teams: list[str],
    points: dict[str, float],
    gd: dict[str, float],
    first_count: dict[str, int],
    second_count: dict[str, int],
    trials: int,
) -> list[TeamStanding]:
    out = []
    for t in teams:
        first_p = first_count[t] / trials
        second_p = second_count[t] / trials
        out.append(
            TeamStanding(
                team=t,
                expected_points=points[t] / trials,
                expected_gd=gd[t] / trials,
                qualify_first_prob=first_p,
                qualify_second_prob=second_p,
                qualify_prob=first_p + second_p,
            )
        )
    return sorted(out, key=lambda s: -s.qualify_prob)


def _knockout_winner(match: KnockoutMatch, rng: np.random.Generator) -> str:
    """Sample a (home, away) score; if tied, fall back to a coin flip."""
    home_g, away_g = simulate_match(match.score_matrix, rng)
    if home_g > away_g:
        return match.team_a
    if away_g > home_g:
        return match.team_b
    # Penalty shoot-out approximation: 50/50 unbiased.
    return match.team_a if rng.random() < 0.5 else match.team_b

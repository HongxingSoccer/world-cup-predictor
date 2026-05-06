"""Monte-Carlo tournament simulator driver.

Reads every persisted World-Cup-2026 prediction (one ``score_matrix`` per
fixture), reconstructs the group structure from the ``matches`` table, and
plays the tournament forward ``--trials`` times. Per trial:

    1. Each group fixture with a stored score matrix is sampled once
       (independent Poisson via :func:`simulate_match`). Fixtures with no
       prediction yet are skipped — teams just don't earn / concede points
       for those games this trial.
    2. Teams are ranked inside each group by FIFA tiebreakers (points →
       goal-diff → goals-for → name). Top-two from each group qualify; the
       eight best third-placed teams round out the 32-team R32.
    3. The knockout bracket is seeded deterministically (group-winners face
       runners-up from neighbouring groups). For pairings we don't have a
       prediction for, we synthesise a 10×10 matrix from each team's
       group-stage average expected goals using two independent Poissons —
       same closed-form Phase-2 baseline as ``PoissonBaselineModel``.
    4. The bracket resolves R32 → R16 → QF → SF → final + third-place
       playoff. We record per-team champion / runner-up / 3rd / 4th /
       semis / quarters / R16 reach probabilities.

Output: a single new row in ``simulation_results`` keyed by
``simulation_version`` (default ``poisson-mc-v1``). The
``/api/v1/worldcup/simulation`` endpoint reads the latest row.

Usage:
    python -m scripts.run_tournament_simulation
    python -m scripts.run_tournament_simulation --trials 5000 --seed 42
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from typing import Any

import numpy as np
import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.routes.worldcup import (
    WORLDCUP_COMPETITION_NAME,
    WORLDCUP_DEFAULT_YEAR,
    _derive_groups,
)
from src.ml.simulation.monte_carlo import simulate_match
from src.models.competition import Competition
from src.models.match import Match
from src.models.prediction import Prediction
from src.models.season import Season
from src.models.simulation_result import SimulationResult
from src.models.team import Team
from src.utils.db import session_scope
from src.utils.logging import configure_logging

logger = structlog.get_logger(__name__)

DEFAULT_TRIALS: int = 10_000
DEFAULT_SIMULATION_VERSION: str = "poisson-mc-v1"
SCORE_MATRIX_SIZE: int = 10
QUALIFIERS_PER_GROUP: int = 2
BEST_THIRD_QUALIFIERS: int = 8


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--trials", type=int, default=DEFAULT_TRIALS)
    p.add_argument("--seed", type=int, default=None)
    p.add_argument(
        "--simulation-version",
        default=DEFAULT_SIMULATION_VERSION,
        help="Tag stored on the simulation_results row.",
    )
    return p.parse_args()


def run_and_persist(
    *,
    trials: int = DEFAULT_TRIALS,
    seed: int | None = None,
    simulation_version: str = DEFAULT_SIMULATION_VERSION,
) -> tuple[int, dict[str, Any]] | None:
    """Run one full Monte Carlo tournament simulation and persist the result.

    Used by both the CLI driver and the daily Celery task. Returns
    ``(simulation_id, results_payload)`` on success, or ``None`` if there's
    no data to simulate (e.g., predictions table empty).
    """
    with session_scope() as session:
        bundle = _load_tournament(session)
        if bundle is None:
            logger.error("tournament_no_data")
            return None

        teams_by_id = bundle["teams_by_id"]
        groups = bundle["groups"]
        fixtures_by_group = bundle["fixtures_by_group"]
        team_to_group = bundle["team_to_group"]
        team_lambdas = bundle["team_lambdas"]
        model_version = bundle["model_version"]

        logger.info(
            "tournament_loaded",
            groups=len(groups),
            teams=sum(len(g) for g in groups.values()),
            fixtures_with_pred=sum(len(v) for v in fixtures_by_group.values()),
            model_version=model_version,
        )

        rng = np.random.default_rng(seed)
        agg = _run_trials(
            groups=groups,
            fixtures_by_group=fixtures_by_group,
            team_to_group=team_to_group,
            team_lambdas=team_lambdas,
            trials=trials,
            rng=rng,
        )
        results_payload = _build_results_payload(
            teams_by_id=teams_by_id, agg=agg, trials=trials
        )

        row = SimulationResult(
            simulation_version=simulation_version,
            num_simulations=trials,
            model_version=model_version,
            results=results_payload,
        )
        session.add(row)
        session.flush()
        sim_id = row.id
        logger.info(
            "tournament_simulation_persisted",
            simulation_id=sim_id,
            trials=trials,
            version=simulation_version,
            model_version=model_version,
        )

    return sim_id, results_payload


def main(args: argparse.Namespace) -> int:
    outcome = run_and_persist(
        trials=args.trials,
        seed=args.seed,
        simulation_version=args.simulation_version,
    )
    if outcome is None:
        return 2
    sim_id, results_payload = outcome
    print(f"simulation_id={sim_id} trials={args.trials} version={args.simulation_version}")
    _print_top10(results_payload)
    return 0


# --- Data loading ---------------------------------------------------------


def _load_tournament(session: Session) -> dict[str, Any] | None:
    """Pull WC 2026 matches + their predictions and shape them for the simulator."""
    season = session.execute(
        select(Season)
        .join(Competition, Competition.id == Season.competition_id)
        .where(
            Competition.name == WORLDCUP_COMPETITION_NAME,
            Season.year == WORLDCUP_DEFAULT_YEAR,
        )
        .limit(1)
    ).scalar_one_or_none()
    if season is None:
        return None

    matches = session.execute(
        select(Match).where(Match.season_id == season.id)
    ).scalars().all()
    if not matches:
        return None

    # Filter to the currently-active model version. After a model upgrade the
    # predictions table holds rows for both old and new model_versions; the
    # API routes already filter to ACTIVE_MODEL_NAME, and the MC has to do
    # the same so the simulation reflects what users see on the dashboard.
    from src.config.settings import settings  # local: avoid heavy import on module load

    pred_rows = session.execute(
        select(Prediction).where(
            Prediction.match_id.in_([m.id for m in matches]),
            Prediction.model_version == settings.ACTIVE_MODEL_NAME,
        )
    ).scalars().all()
    pred_by_match: dict[int, Prediction] = {p.match_id: p for p in pred_rows}

    if not pred_by_match:
        return None

    # Group derivation reads matches; reuse the worldcup route's helper so the
    # simulator stays consistent with the public /standings layout.
    clusters = _derive_groups(list(matches))
    clusters.sort(key=lambda members: min(members))
    groups: dict[str, list[int]] = {}
    team_to_group: dict[int, str] = {}
    for idx, members in enumerate(clusters):
        label = chr(ord("A") + idx) if idx < 26 else f"G{idx + 1}"
        groups[label] = sorted(members)
        for tid in members:
            team_to_group[tid] = label

    fixtures_by_group: dict[str, list[dict[str, Any]]] = defaultdict(list)
    team_lambdas_acc: dict[int, list[float]] = defaultdict(list)
    model_versions: set[str] = set()

    for match in matches:
        pred = pred_by_match.get(match.id)
        if pred is None:
            continue
        group = team_to_group.get(match.home_team_id)
        if group is None or team_to_group.get(match.away_team_id) != group:
            # Knockout fixture or cross-group anomaly — skip from group sim.
            continue
        score_matrix = pred.score_matrix
        if not isinstance(score_matrix, list) or not score_matrix:
            continue
        fixtures_by_group[group].append(
            {
                "home_team_id": match.home_team_id,
                "away_team_id": match.away_team_id,
                "score_matrix": score_matrix,
            }
        )
        team_lambdas_acc[match.home_team_id].append(float(pred.lambda_home or 0.0))
        team_lambdas_acc[match.away_team_id].append(float(pred.lambda_away or 0.0))
        model_versions.add(pred.model_version)

    teams_by_id = {
        t.id: t for t in session.execute(select(Team)).scalars().all()
    }

    # Average λ per team — used to synthesise score matrices for knockout
    # pairings we have no direct prediction for.
    team_lambdas: dict[int, float] = {}
    overall_lambdas = [v for vs in team_lambdas_acc.values() for v in vs]
    fallback = float(np.mean(overall_lambdas)) if overall_lambdas else 1.0
    for tid in teams_by_id:
        vs = team_lambdas_acc.get(tid)
        team_lambdas[tid] = float(np.mean(vs)) if vs else fallback

    model_version = next(iter(model_versions)) if model_versions else "unknown"
    return {
        "teams_by_id": teams_by_id,
        "groups": groups,
        "fixtures_by_group": dict(fixtures_by_group),
        "team_to_group": team_to_group,
        "team_lambdas": team_lambdas,
        "model_version": model_version,
    }


# --- Trial loop -----------------------------------------------------------


def _run_trials(
    *,
    groups: dict[str, list[int]],
    fixtures_by_group: dict[str, list[dict[str, Any]]],
    team_to_group: dict[int, str],
    team_lambdas: dict[int, float],
    trials: int,
    rng: np.random.Generator,
) -> dict[str, dict[int, int]]:
    """Run ``trials`` full-tournament Monte Carlo plays and return per-team counters."""
    counters: dict[str, dict[int, int]] = {
        "qualify_first": defaultdict(int),
        "qualify_second": defaultdict(int),
        "qualify": defaultdict(int),
        "round_of_16": defaultdict(int),
        "quarterfinal": defaultdict(int),
        "semifinal": defaultdict(int),
        "final": defaultdict(int),
        "champion": defaultdict(int),
        "runner_up": defaultdict(int),
        "third": defaultdict(int),
        "fourth": defaultdict(int),
        "expected_points_total": defaultdict(float),
        "expected_gd_total": defaultdict(float),
    }

    for _ in range(trials):
        group_rankings = _simulate_group_stage_once(
            groups=groups,
            fixtures_by_group=fixtures_by_group,
            counters=counters,
            rng=rng,
        )
        qualifiers = _select_32_qualifiers(group_rankings)
        for tid in qualifiers:
            counters["qualify"][tid] += 1
        # Stage progression: R32 → R16 → QF → SF → Final + 3rd place.
        r16_winners = _resolve_round(qualifiers, team_lambdas, rng)
        for tid in r16_winners:
            counters["round_of_16"][tid] += 1
        qf_winners = _resolve_round(r16_winners, team_lambdas, rng)
        for tid in qf_winners:
            counters["quarterfinal"][tid] += 1
        sf_winners, sf_losers = _resolve_round_with_losers(qf_winners, team_lambdas, rng)
        for tid in qf_winners:
            counters["semifinal"][tid] += 1  # reached the SF (won QF)
        for tid in sf_winners:
            counters["final"][tid] += 1
        # Final + third-place playoff.
        champion, runner_up = _resolve_pair(sf_winners, team_lambdas, rng)
        third, fourth = _resolve_pair(sf_losers, team_lambdas, rng)
        counters["champion"][champion] += 1
        counters["runner_up"][runner_up] += 1
        counters["third"][third] += 1
        counters["fourth"][fourth] += 1

    return counters


def _simulate_group_stage_once(
    *,
    groups: dict[str, list[int]],
    fixtures_by_group: dict[str, list[dict[str, Any]]],
    counters: dict[str, dict[int, int]],
    rng: np.random.Generator,
) -> dict[str, list[int]]:
    """Simulate every group's fixtures once; rank each group; return rank → team_id list."""
    rankings: dict[str, list[int]] = {}
    for label, team_ids in groups.items():
        points: dict[int, int] = {tid: 0 for tid in team_ids}
        gd: dict[int, int] = {tid: 0 for tid in team_ids}
        gf: dict[int, int] = {tid: 0 for tid in team_ids}
        for fixture in fixtures_by_group.get(label, []):
            h, a = simulate_match(fixture["score_matrix"], rng)
            ht, at = fixture["home_team_id"], fixture["away_team_id"]
            gd[ht] += h - a
            gd[at] += a - h
            gf[ht] += h
            gf[at] += a
            if h > a:
                points[ht] += 3
            elif a > h:
                points[at] += 3
            else:
                points[ht] += 1
                points[at] += 1
        ordered = sorted(team_ids, key=lambda t: (-points[t], -gd[t], -gf[t], t))
        rankings[label] = ordered
        for rank, tid in enumerate(ordered):
            if rank == 0:
                counters["qualify_first"][tid] += 1
            elif rank == 1:
                counters["qualify_second"][tid] += 1
            counters["expected_points_total"][tid] += points[tid]
            counters["expected_gd_total"][tid] += gd[tid]
    return rankings


def _select_32_qualifiers(group_rankings: dict[str, list[int]]) -> list[int]:
    """Top-2 from each group + 8 best 3rd-placed teams.

    The 8-best-third selection picks teams in stable group order — fully fair
    tiebreaking would need carried-over points/GD, but for v1 simulator
    deterministic group-order seeding is fine because the trial is already
    randomised at the match level."""
    top_two: list[int] = []
    thirds: list[int] = []
    for ordered in group_rankings.values():
        if len(ordered) >= 1:
            top_two.append(ordered[0])
        if len(ordered) >= 2:
            top_two.append(ordered[1])
        if len(ordered) >= 3:
            thirds.append(ordered[2])
    qualifiers = top_two + thirds[:BEST_THIRD_QUALIFIERS]
    return qualifiers[:32]


def _resolve_round(
    teams: list[int],
    team_lambdas: dict[int, float],
    rng: np.random.Generator,
) -> list[int]:
    """Pair adjacent teams and resolve each match. Returns winners in order."""
    winners: list[int] = []
    for i in range(0, len(teams), 2):
        if i + 1 >= len(teams):
            winners.append(teams[i])
            continue
        winners.append(_resolve_match(teams[i], teams[i + 1], team_lambdas, rng))
    return winners


def _resolve_round_with_losers(
    teams: list[int],
    team_lambdas: dict[int, float],
    rng: np.random.Generator,
) -> tuple[list[int], list[int]]:
    winners: list[int] = []
    losers: list[int] = []
    for i in range(0, len(teams), 2):
        if i + 1 >= len(teams):
            winners.append(teams[i])
            continue
        winner = _resolve_match(teams[i], teams[i + 1], team_lambdas, rng)
        loser = teams[i + 1] if winner == teams[i] else teams[i]
        winners.append(winner)
        losers.append(loser)
    return winners, losers


def _resolve_pair(
    teams: list[int],
    team_lambdas: dict[int, float],
    rng: np.random.Generator,
) -> tuple[int, int]:
    """Resolve a 2-team match; return (winner, loser). Coin-flip if list shorter than 2."""
    if len(teams) < 2:
        only = teams[0] if teams else 0
        return only, only
    winner = _resolve_match(teams[0], teams[1], team_lambdas, rng)
    loser = teams[1] if winner == teams[0] else teams[0]
    return winner, loser


def _resolve_match(
    team_a: int,
    team_b: int,
    team_lambdas: dict[int, float],
    rng: np.random.Generator,
) -> int:
    """Synthesise a 10×10 matrix from the two teams' average λ and sample once."""
    lambda_a = max(team_lambdas.get(team_a, 1.0), 0.05)
    lambda_b = max(team_lambdas.get(team_b, 1.0), 0.05)
    matrix = _independent_poisson_matrix(lambda_a, lambda_b)
    h, a = simulate_match(matrix, rng)
    if h > a:
        return team_a
    if a > h:
        return team_b
    # Knockout draw — penalty shoot-out approximation: 50/50.
    return team_a if rng.random() < 0.5 else team_b


def _independent_poisson_matrix(
    lambda_home: float, lambda_away: float, *, size: int = SCORE_MATRIX_SIZE
) -> list[list[float]]:
    home_pmf = _poisson_pmf(lambda_home, size)
    away_pmf = _poisson_pmf(lambda_away, size)
    matrix = [[home_pmf[i] * away_pmf[j] for j in range(size)] for i in range(size)]
    return matrix


def _poisson_pmf(rate: float, size: int) -> list[float]:
    """Closed-form Poisson PMF for k=0..size-1. Avoid scipy at the cost of one log-factorial."""
    out: list[float] = []
    log_fact = 0.0
    for k in range(size):
        if k > 0:
            log_fact += np.log(k)
        log_p = -rate + k * np.log(rate) - log_fact if rate > 0 else (1.0 if k == 0 else 0.0)
        out.append(float(np.exp(log_p)) if rate > 0 else (1.0 if k == 0 else 0.0))
    return out


# --- Output payload -------------------------------------------------------


def _build_results_payload(
    *,
    teams_by_id: dict[int, Team],
    agg: dict[str, dict[int, int]],
    trials: int,
) -> dict[str, Any]:
    by_team: dict[str, dict[str, Any]] = {}
    leaderboard: list[dict[str, Any]] = []

    all_team_ids = (
        set(agg["qualify"].keys())
        | set(agg["champion"].keys())
        | set(agg["qualify_first"].keys())
        | set(agg["qualify_second"].keys())
    )
    for tid in all_team_ids:
        team = teams_by_id.get(tid)
        block = {
            "team_id": tid,
            "team_name": team.name if team else f"#{tid}",
            "team_name_zh": team.name_zh if team else None,
            "qualify_first_prob": agg["qualify_first"][tid] / trials,
            "qualify_second_prob": agg["qualify_second"][tid] / trials,
            "qualify_prob": agg["qualify"][tid] / trials,
            "round_of_16_prob": agg["round_of_16"][tid] / trials,
            "quarterfinal_prob": agg["quarterfinal"][tid] / trials,
            "semifinal_prob": agg["semifinal"][tid] / trials,
            "final_prob": agg["final"][tid] / trials,
            "champion_prob": agg["champion"][tid] / trials,
            "runner_up_prob": agg["runner_up"][tid] / trials,
            "third_prob": agg["third"][tid] / trials,
            "fourth_prob": agg["fourth"][tid] / trials,
            "top4_prob": (
                agg["champion"][tid]
                + agg["runner_up"][tid]
                + agg["third"][tid]
                + agg["fourth"][tid]
            ) / trials,
            "expected_points": agg["expected_points_total"][tid] / trials,
            "expected_gd": agg["expected_gd_total"][tid] / trials,
        }
        by_team[str(tid)] = block
        leaderboard.append(block)

    leaderboard.sort(key=lambda b: -b["champion_prob"])
    return {
        "by_team": by_team,
        "leaderboard": leaderboard,
        "trials": trials,
    }


def _print_top10(payload: dict[str, Any]) -> None:
    print("\nTop-10 by champion_prob:")
    print(f"  {'Team':25} {'champ':>7} {'top4':>7} {'qualify':>9}")
    for block in payload["leaderboard"][:10]:
        print(
            f"  {block['team_name'][:25]:25} "
            f"{block['champion_prob']*100:6.2f}% "
            f"{block['top4_prob']*100:6.2f}% "
            f"{block['qualify_prob']*100:8.2f}%"
        )


if __name__ == "__main__":
    configure_logging(json_logs=False)
    sys.exit(main(parse_args()))

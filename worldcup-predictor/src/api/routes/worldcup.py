"""GET /api/v1/worldcup/simulation, /worldcup/team/{id}/path — Phase 4 endpoints.

Reads the latest row from ``simulation_results`` (one JSONB blob per run
holds every team's per-stage probabilities). The bracket page consumes
``/simulation``; per-team detail pages consume ``/team/{id}/path``.

Also exposes the static ``/competitions/worldcup/standings`` and
``/competitions/worldcup/bracket`` endpoints used by the public worldcup
pages — these derive group membership from the matches table (so the data
is correct as soon as the draw is ingested) and compute live standings from
finished matches.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.dependencies import get_db_session
from src.models.competition import Competition
from src.models.match import Match
from src.models.prediction import Prediction
from src.models.season import Season
from src.models.simulation_result import SimulationResult
from src.models.team import Team

router = APIRouter(prefix="/api/v1/worldcup", tags=["worldcup"])

# Separate router for the public competitions namespace consumed by Java's
# CompetitionController. Kept distinct from the /worldcup prefix so the URL
# matches what the frontend already calls.
competitions_router = APIRouter(prefix="/api/v1/competitions", tags=["competitions"])

WORLDCUP_COMPETITION_NAME = "FIFA World Cup"
WORLDCUP_DEFAULT_YEAR = 2026


def _latest(session: Session) -> SimulationResult:
    row = (
        session.query(SimulationResult)
        .order_by(SimulationResult.computed_at.desc())
        .first()
    )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": 40400, "error": "SIMULATION_NOT_FOUND"},
        )
    return row


@router.get("/simulation")
def get_latest_simulation(session: Session = Depends(get_db_session)) -> dict:
    """Return the latest tournament simulation snapshot."""
    row = _latest(session)
    return {
        "id": row.id,
        "simulation_version": row.simulation_version,
        "num_simulations": row.num_simulations,
        "model_version": row.model_version,
        "results": row.results,
        "computed_at": row.computed_at.isoformat(),
    }


@router.get("/team/{team_id}/path")
def get_team_path(
    team_id: int, session: Session = Depends(get_db_session)
) -> dict:
    """Return per-stage probabilities for one team (group → champion)."""
    row = _latest(session)
    by_team = (row.results or {}).get("by_team", {})
    team_block = by_team.get(str(team_id)) or by_team.get(team_id)
    if team_block is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": 40400, "error": "TEAM_NOT_IN_SIMULATION"},
        )
    return {
        "team_id": team_id,
        "simulation_id": row.id,
        "simulation_version": row.simulation_version,
        "computed_at": row.computed_at.isoformat(),
        "path": team_block,
    }


# --- Public competitions endpoints (consumed by Java CompetitionController) -


def _worldcup_season(session: Session) -> Season | None:
    """Find the canonical (FIFA World Cup, year=DEFAULT) season row."""
    return session.execute(
        select(Season)
        .join(Competition, Competition.id == Season.competition_id)
        .where(
            Competition.name == WORLDCUP_COMPETITION_NAME,
            Season.year == WORLDCUP_DEFAULT_YEAR,
        )
        .limit(1)
    ).scalar_one_or_none()


def _derive_groups(matches: list[Match]) -> list[set[int]]:
    """Cluster team ids into groups via union-find on group-stage opponents.

    The first round of fixtures defines the group structure: every team plays
    its 3 group-mates exactly once before the knockout stage. We treat the
    *earliest* matches (by date) as the group stage and stop once each team
    has been seen in 3 distinct opponent pairings — past that the bracket
    starts and would otherwise leak knockout edges into the groups.
    """
    parent: dict[int, int] = {}

    def find(x: int) -> int:
        while parent.get(x, x) != x:
            parent[x] = parent.get(parent.get(x, x), parent.get(x, x))
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    opponent_count: dict[int, int] = defaultdict(int)
    seen_pairs: set[tuple[int, int]] = set()

    for match in sorted(matches, key=lambda m: m.match_date):
        a, b = sorted((match.home_team_id, match.away_team_id))
        if (a, b) in seen_pairs:
            continue
        # Once a team has 3 group-stage opponents recorded, additional games
        # are knockout fixtures and must not be unioned.
        if opponent_count[a] >= 3 or opponent_count[b] >= 3:
            continue
        seen_pairs.add((a, b))
        opponent_count[a] += 1
        opponent_count[b] += 1
        parent.setdefault(a, a)
        parent.setdefault(b, b)
        union(a, b)

    groups: dict[int, set[int]] = defaultdict(set)
    for team_id in parent:
        groups[find(team_id)].add(team_id)
    # Filter to only cohesive groups (3-4 members); junk singletons fall out.
    return [members for members in groups.values() if 2 <= len(members) <= 4]


def _compute_standings(
    session: Session, group_team_ids: set[int], all_matches: list[Match]
) -> list[dict[str, Any]]:
    """Return one row per team in the group sorted by FIFA tiebreakers."""
    teams = {
        t.id: t
        for t in session.query(Team).filter(Team.id.in_(group_team_ids)).all()
    }
    stats: dict[int, dict[str, Any]] = {
        tid: {
            "team_id": tid,
            "team_name": teams[tid].name if tid in teams else f"#{tid}",
            "team_name_zh": teams[tid].name_zh if tid in teams else None,
            "played": 0,
            "wins": 0,
            "draws": 0,
            "losses": 0,
            "goals_for": 0,
            "goals_against": 0,
        }
        for tid in group_team_ids
    }

    for match in all_matches:
        if match.status != "finished":
            continue
        if match.home_score is None or match.away_score is None:
            continue
        h, a = match.home_team_id, match.away_team_id
        if h not in stats or a not in stats:
            continue
        hs, as_ = int(match.home_score), int(match.away_score)
        stats[h]["played"] += 1
        stats[a]["played"] += 1
        stats[h]["goals_for"] += hs
        stats[h]["goals_against"] += as_
        stats[a]["goals_for"] += as_
        stats[a]["goals_against"] += hs
        if hs > as_:
            stats[h]["wins"] += 1
            stats[a]["losses"] += 1
        elif hs < as_:
            stats[a]["wins"] += 1
            stats[h]["losses"] += 1
        else:
            stats[h]["draws"] += 1
            stats[a]["draws"] += 1

    rows = []
    for s in stats.values():
        s["goal_diff"] = s["goals_for"] - s["goals_against"]
        s["points"] = s["wins"] * 3 + s["draws"]
        rows.append(s)
    # FIFA group-stage tiebreakers (simplified): points → GD → GF → name.
    rows.sort(
        key=lambda r: (-r["points"], -r["goal_diff"], -r["goals_for"], r["team_name"])
    )
    for idx, row in enumerate(rows, start=1):
        row["position"] = idx
    return rows


@competitions_router.get("/worldcup/standings")
def worldcup_standings(session: Session = Depends(get_db_session)) -> dict[str, Any]:
    """Return derived group standings for the FIFA World Cup season."""
    season = _worldcup_season(session)
    if season is None:
        return {"groups": [], "competition": WORLDCUP_COMPETITION_NAME, "year": WORLDCUP_DEFAULT_YEAR}

    matches = session.query(Match).filter(Match.season_id == season.id).all()
    if not matches:
        return {"groups": [], "competition": WORLDCUP_COMPETITION_NAME, "year": season.year}

    clusters = _derive_groups(matches)
    # Letter the groups in stable team-id order so labels don't shuffle on re-run.
    clusters.sort(key=lambda members: min(members))

    groups_payload: list[dict[str, Any]] = []
    for idx, members in enumerate(clusters):
        label = chr(ord("A") + idx) if idx < 26 else f"G{idx + 1}"
        rows = _compute_standings(session, members, matches)
        groups_payload.append({"name": label, "rows": rows})
    return {
        "competition": WORLDCUP_COMPETITION_NAME,
        "year": season.year,
        "groups": groups_payload,
    }


def _classify_round(match: Match, total_matches: int) -> str:
    """Bucket a fixture into group / R16 / QF / SF / Final based on date order.

    A clean WC has 48 group-stage matches then 32 knockout matches. We sort
    by date and slot them into the canonical structure rather than trusting
    a `round` column we don't reliably populate.
    """
    return "group"  # Default; real bucketing happens in :func:`worldcup_bracket`.


@competitions_router.get("/worldcup/bracket")
def worldcup_bracket(session: Session = Depends(get_db_session)) -> dict[str, Any]:
    """Return matches grouped into knockout rounds with predictions inline.

    With WC2026's 48-team format the first 72 matches are group stage; the
    remaining 32 are knockout (R32 → R16 → QF → SF → 3rd-place + Final). We
    return a deterministic ordered list of rounds; rounds without ingested
    fixtures yet show as ``status='tbd'`` placeholders so the UI can still
    render the bracket scaffold.
    """
    season = _worldcup_season(session)
    response: dict[str, Any] = {
        "competition": WORLDCUP_COMPETITION_NAME,
        "year": WORLDCUP_DEFAULT_YEAR,
        "rounds": [],
        "generated_at": datetime.now(UTC).isoformat(),
    }
    if season is None:
        response["rounds"] = _empty_bracket_scaffold()
        return response

    response["year"] = season.year
    matches = (
        session.query(Match)
        .filter(Match.season_id == season.id)
        .order_by(Match.match_date)
        .all()
    )
    if not matches:
        response["rounds"] = _empty_bracket_scaffold()
        return response

    # Pull predictions in one query so we can decorate the response.
    pred_by_match: dict[int, Prediction] = {}
    pred_rows = (
        session.query(Prediction)
        .filter(Prediction.match_id.in_([m.id for m in matches]))
        .all()
    )
    # Keep the highest-confidence prediction per match.
    for p in pred_rows:
        existing = pred_by_match.get(p.match_id)
        if existing is None or (p.confidence_score or 0) > (existing.confidence_score or 0):
            pred_by_match[p.match_id] = p

    teams = {t.id: t for t in session.query(Team).all()}

    # 48-team structure: 72 group + 32 knockout = 104 matches total.
    # Knockout bucketing: 16 R32 → 8 R16 → 4 QF → 2 SF → 1 third-place → 1 Final.
    GROUP_STAGE_END = 72
    knockout = matches[GROUP_STAGE_END:]
    bracket_buckets: list[tuple[str, int, int]] = [
        ("32 强", 0, 16),
        ("16 强", 16, 24),
        ("8 强", 24, 28),
        ("4 强", 28, 30),
        ("3/4 名", 30, 31),
        ("决赛", 31, 32),
    ]
    rounds: list[dict[str, Any]] = []
    for label, start, end in bracket_buckets:
        round_matches = knockout[start:end] if start < len(knockout) else []
        capacity = end - start
        # Pad with TBD placeholders so the bracket UI always has the right shape.
        while len(round_matches) < capacity:
            round_matches.append(None)  # type: ignore[arg-type]
        rounds.append(
            {
                "label": label,
                "matches": [
                    _bracket_match_payload(m, teams, pred_by_match)
                    for m in round_matches
                ],
            }
        )
    response["rounds"] = rounds
    return response


def _empty_bracket_scaffold() -> list[dict[str, Any]]:
    return [
        {"label": label, "matches": [_tbd_match() for _ in range(count)]}
        for label, count in (
            ("32 强", 16),
            ("16 强", 8),
            ("8 强", 4),
            ("4 强", 2),
            ("3/4 名", 1),
            ("决赛", 1),
        )
    ]


def _tbd_match() -> dict[str, Any]:
    return {
        "match_id": None,
        "home_team": None,
        "away_team": None,
        "home_score": None,
        "away_score": None,
        "status": "tbd",
        "prob_home_win": None,
        "prob_away_win": None,
    }


def _bracket_match_payload(
    match: Match | None,
    teams: dict[int, Team],
    predictions: dict[int, Prediction],
) -> dict[str, Any]:
    if match is None:
        return _tbd_match()
    home = teams.get(match.home_team_id)
    away = teams.get(match.away_team_id)
    pred = predictions.get(match.id)
    return {
        "match_id": match.id,
        "match_date": match.match_date.isoformat() if match.match_date else None,
        "home_team": home.name if home else None,
        "away_team": away.name if away else None,
        "home_score": match.home_score,
        "away_score": match.away_score,
        "status": match.status or "scheduled",
        "prob_home_win": float(pred.prob_home_win) if pred else None,
        "prob_away_win": float(pred.prob_away_win) if pred else None,
    }

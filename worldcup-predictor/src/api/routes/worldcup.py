"""GET /api/v1/worldcup/simulation, /worldcup/team/{id}/path — Phase 4 endpoints.

Reads the latest row from ``simulation_results`` (one JSONB blob per run
holds every team's per-stage probabilities). The bracket page consumes
``/simulation``; per-team detail pages consume ``/team/{id}/path``.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.api.dependencies import get_db_session
from src.models.simulation_result import SimulationResult

router = APIRouter(prefix="/api/v1/worldcup", tags=["worldcup"])


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

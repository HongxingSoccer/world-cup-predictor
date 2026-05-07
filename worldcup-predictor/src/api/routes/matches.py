"""GET /api/v1/matches/{id} — pure read of match metadata + cached prediction.

Distinct from POST /api/v1/predict: this never runs the model. Returns whatever
already exists in the DB so the public match-detail page can render even when
features are missing or the prediction hasn't been computed yet. Bundles
recent form (last 5 matches per side) and a head-to-head summary so the
frontend doesn't need a second round-trip.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import and_, desc, or_, select
from sqlalchemy.orm import Session

from src.api.dependencies import get_db_session
from src.config.settings import settings
from src.models.h2h_record import H2HRecord
from src.models.match import Match
from src.models.odds_analysis import OddsAnalysis
from src.models.prediction import Prediction
from src.models.season import Season
from src.models.team import Team

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/v1/matches", tags=["matches"])

FORM_WINDOW: int = 5  # last N finished matches per side


class TeamFormRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    home: str
    away: str


class H2HSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_matches: int
    home_wins: int
    draws: int
    away_wins: int
    avg_goals: float
    last_match_date: Optional[str] = None


class MatchDetailResponse(BaseModel):
    """Read-only match-detail payload. snake_case mirrors PredictionTodayItem."""

    model_config = ConfigDict(extra="forbid")

    match_id: int
    match_date: datetime
    home_team: str
    away_team: str
    competition: Optional[str]
    venue: Optional[str]
    round: Optional[str]
    status: str
    home_score: Optional[int]
    away_score: Optional[int]

    # Latest active-model prediction (None when no row exists yet).
    prob_home_win: Optional[float] = None
    prob_draw: Optional[float] = None
    prob_away_win: Optional[float] = None
    confidence_score: Optional[int] = None
    confidence_level: Optional[str] = None
    has_value_signal: Optional[bool] = None
    top_signal_level: Optional[int] = None
    score_matrix: Optional[list[list[float]]] = None
    over_under_probs: Optional[dict[str, dict[str, float]]] = None
    btts_prob: Optional[float] = None
    odds_analysis: Optional[list[dict[str, Any]]] = None

    team_stats: list[TeamFormRow] = Field(default_factory=list)
    h2h: H2HSummary
    locked: bool = False


@router.get("/{match_id}", response_model=MatchDetailResponse)
def match_detail(
    match_id: int,
    db_session: Session = Depends(get_db_session),
) -> MatchDetailResponse:
    """Return one match's metadata, latest prediction, recent form, and H2H summary."""
    match = db_session.get(Match, match_id)
    if match is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"match {match_id} not found",
        )

    home_team = db_session.get(Team, match.home_team_id)
    away_team = db_session.get(Team, match.away_team_id)
    season = db_session.get(Season, match.season_id) if match.season_id else None

    prediction = _latest_prediction(db_session, match_id)
    odds_rows = (
        _odds_analysis_rows(db_session, prediction.id) if prediction is not None else []
    )
    top_signal = max((row["signal_level"] for row in odds_rows), default=0)

    form_rows = _team_form_rows(db_session, match)
    h2h = _h2h_summary(db_session, match.home_team_id, match.away_team_id)

    return MatchDetailResponse(
        match_id=match.id,
        match_date=match.match_date,
        home_team=_team_label(home_team),
        away_team=_team_label(away_team),
        competition=str(season.year) if season and season.year else None,
        venue=match.venue,
        round=match.round,
        status=match.status,
        home_score=match.home_score,
        away_score=match.away_score,
        prob_home_win=float(prediction.prob_home_win) if prediction else None,
        prob_draw=float(prediction.prob_draw) if prediction else None,
        prob_away_win=float(prediction.prob_away_win) if prediction else None,
        confidence_score=int(prediction.confidence_score) if prediction else None,
        confidence_level=prediction.confidence_level if prediction else None,
        has_value_signal=top_signal > 0 if prediction else None,
        top_signal_level=top_signal if prediction else None,
        score_matrix=prediction.score_matrix if prediction else None,
        over_under_probs=prediction.over_under_probs if prediction else None,
        btts_prob=float(prediction.btts_prob)
        if prediction and prediction.btts_prob is not None
        else None,
        odds_analysis=odds_rows if prediction else None,
        team_stats=form_rows,
        h2h=h2h,
        locked=False,
    )


# --- Internal helpers ------------------------------------------------------


def _team_label(team: Optional[Team]) -> str:
    if team is None:
        return "?"
    return team.name_zh or team.name


def _latest_prediction(session: Session, match_id: int) -> Optional[Prediction]:
    stmt = (
        select(Prediction)
        .where(
            Prediction.match_id == match_id,
            Prediction.model_version == settings.ACTIVE_MODEL_NAME,
        )
        .order_by(desc(Prediction.published_at))
        .limit(1)
    )
    return session.execute(stmt).scalar_one_or_none()


def _odds_analysis_rows(session: Session, prediction_id: int) -> list[dict[str, Any]]:
    rows = (
        session.execute(
            select(OddsAnalysis)
            .where(OddsAnalysis.prediction_id == prediction_id)
            .order_by(desc(OddsAnalysis.signal_level))
        )
        .scalars()
        .all()
    )
    return [
        {
            "id": row.id,
            "market_type": row.market_type,
            "market_value": row.market_value,
            "outcome": row.outcome,
            "model_prob": float(row.model_prob),
            "best_odds": float(row.best_odds),
            "best_bookmaker": row.best_bookmaker,
            "implied_prob": float(row.implied_prob),
            "ev": float(row.ev),
            "edge": float(row.edge),
            "signal_level": int(row.signal_level),
        }
        for row in rows
    ]


def _team_form_rows(session: Session, match: Match) -> list[TeamFormRow]:
    """Last-5-finished-matches summary per side, formatted for the UI table."""
    home_form = _recent_form(session, match.home_team_id, before=match.match_date)
    away_form = _recent_form(session, match.away_team_id, before=match.match_date)
    if home_form["count"] == 0 and away_form["count"] == 0:
        return []
    return [
        TeamFormRow(
            label=f"近{FORM_WINDOW}场胜率",
            home=_pct_str(home_form["wins"], home_form["count"]),
            away=_pct_str(away_form["wins"], away_form["count"]),
        ),
        TeamFormRow(
            label=f"近{FORM_WINDOW}场均进球",
            home=_avg_str(home_form["goals_for"], home_form["count"]),
            away=_avg_str(away_form["goals_for"], away_form["count"]),
        ),
        TeamFormRow(
            label=f"近{FORM_WINDOW}场均失球",
            home=_avg_str(home_form["goals_against"], home_form["count"]),
            away=_avg_str(away_form["goals_against"], away_form["count"]),
        ),
    ]


def _recent_form(
    session: Session, team_id: int, *, before: datetime
) -> dict[str, int]:
    """Aggregate W/L/D + goals-for/against from the last N finished matches."""
    stmt = (
        select(Match)
        .where(
            and_(
                or_(Match.home_team_id == team_id, Match.away_team_id == team_id),
                Match.status == "finished",
                Match.match_date < before,
                Match.home_score.is_not(None),
                Match.away_score.is_not(None),
            )
        )
        .order_by(desc(Match.match_date))
        .limit(FORM_WINDOW)
    )
    rows = session.execute(stmt).scalars().all()
    wins = goals_for = goals_against = 0
    for m in rows:
        is_home = m.home_team_id == team_id
        own_score = m.home_score if is_home else m.away_score
        opp_score = m.away_score if is_home else m.home_score
        if own_score is None or opp_score is None:
            continue
        goals_for += int(own_score)
        goals_against += int(opp_score)
        if own_score > opp_score:
            wins += 1
    return {
        "count": len(rows),
        "wins": wins,
        "goals_for": goals_for,
        "goals_against": goals_against,
    }


def _h2h_summary(session: Session, home_team_id: int, away_team_id: int) -> H2HSummary:
    """Look up canonical (team_a < team_b) H2H row, normalised to home/away orientation."""
    a_id, b_id = sorted([home_team_id, away_team_id])
    record = session.execute(
        select(H2HRecord).where(
            H2HRecord.team_a_id == a_id, H2HRecord.team_b_id == b_id
        )
    ).scalar_one_or_none()
    if record is None or record.total_matches == 0:
        return H2HSummary(
            total_matches=0, home_wins=0, draws=0, away_wins=0, avg_goals=0.0
        )

    if home_team_id == record.team_a_id:
        home_wins, away_wins = record.team_a_wins, record.team_b_wins
        home_goals, away_goals = record.team_a_goals, record.team_b_goals
    else:
        home_wins, away_wins = record.team_b_wins, record.team_a_wins
        home_goals, away_goals = record.team_b_goals, record.team_a_goals

    avg = (home_goals + away_goals) / record.total_matches if record.total_matches else 0.0
    return H2HSummary(
        total_matches=int(record.total_matches),
        home_wins=int(home_wins),
        draws=int(record.draws),
        away_wins=int(away_wins),
        avg_goals=round(float(avg), 2),
        last_match_date=record.last_match_date.isoformat() if record.last_match_date else None,
    )


def _pct_str(numerator: int, denominator: int) -> str:
    if denominator <= 0:
        return "—"
    return f"{round(numerator * 100 / denominator)}%"


def _avg_str(total: int, denominator: int) -> str:
    if denominator <= 0:
        return "—"
    return f"{total / denominator:.1f}"

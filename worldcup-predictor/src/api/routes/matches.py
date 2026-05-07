"""GET /api/v1/matches/{id} — pure read of match metadata + cached prediction.

Distinct from POST /api/v1/predict: this never runs the model. Returns whatever
already exists in the DB so the public match-detail page can render even when
features are missing or the prediction hasn't been computed yet. Bundles
recent form (last 5 matches per side) and a head-to-head summary so the
frontend doesn't need a second round-trip.

Two companion routes live in this file:
- ``GET /api/v1/matches?ids=1,2,3`` — batch lookup powering the
  "我的收藏" card on the profile page.
- ``GET /api/v1/matches/{id}/related`` — same-round / same-season
  siblings shown beneath the match-detail body.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
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
    home_team_logo: Optional[str] = None
    away_team_logo: Optional[str] = None
    home_team_name_zh: Optional[str] = None
    away_team_name_zh: Optional[str] = None
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
        home_team_logo=home_team.logo_url if home_team else None,
        away_team_logo=away_team.logo_url if away_team else None,
        home_team_name_zh=home_team.name_zh if home_team else None,
        away_team_name_zh=away_team.name_zh if away_team else None,
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


# --- Batch lookup + related-matches ---------------------------------------


class MatchSummary(BaseModel):
    """Compact match payload used by the batch + related routes.

    Distinct from MatchDetailResponse (which carries form / H2H / odds).
    Keep this lean — favorite cards and "same group" siblings render a card
    grid where dozens of these can be on screen at once.
    """

    model_config = ConfigDict(extra="forbid")

    match_id: int
    match_date: datetime
    home_team: str
    away_team: str
    home_team_logo: Optional[str] = None
    away_team_logo: Optional[str] = None
    competition: Optional[str] = None
    status: str
    round: Optional[str] = None
    venue: Optional[str] = None
    home_score: Optional[int] = None
    away_score: Optional[int] = None
    prob_home_win: Optional[float] = None
    prob_draw: Optional[float] = None
    prob_away_win: Optional[float] = None
    confidence_score: Optional[int] = None


@router.get("", response_model=list[MatchSummary])
def matches_batch(
    ids: str = Query(default="", description="Comma-separated match ids."),
    db_session: Session = Depends(get_db_session),
) -> list[MatchSummary]:
    """Bulk-read matches by id list. Powers profile favourites in one round-trip."""
    parsed = _parse_id_list(ids)
    if not parsed:
        return []
    return _summaries_for(db_session, parsed)


@router.get("/{match_id}/related", response_model=list[MatchSummary])
def match_related(
    match_id: int,
    limit: int = Query(default=6, ge=1, le=20),
    db_session: Session = Depends(get_db_session),
) -> list[MatchSummary]:
    """Sibling matches in the same season (and round when available).

    Falls back to season-only matches if the source has no round set, so
    pre-tournament rows without a knockout label still surface a meaningful
    list. The source match itself is excluded.
    """
    source = db_session.get(Match, match_id)
    if source is None:
        return []
    stmt = (
        select(Match)
        .where(Match.season_id == source.season_id, Match.id != source.id)
        .order_by(Match.match_date)
        .limit(limit)
    )
    if source.round:
        stmt = stmt.where(Match.round == source.round)
    sibling_ids = [m.id for m in db_session.execute(stmt).scalars().all()]
    if not sibling_ids:
        return []
    return _summaries_for(db_session, sibling_ids)


def _parse_id_list(raw: str) -> list[int]:
    """Coerce a comma-separated string of ids to a deduped list, ignoring noise."""
    out: list[int] = []
    seen: set[int] = set()
    for part in raw.split(","):
        cleaned = part.strip()
        if not cleaned:
            continue
        try:
            value = int(cleaned)
        except ValueError:
            continue
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
        if len(out) >= 50:  # cap to defend the DB
            break
    return out


def _summaries_for(session: Session, match_ids: list[int]) -> list[MatchSummary]:
    """Build lightweight MatchSummary rows preserving caller-supplied id order."""
    HomeTeam = Team.__table__.alias("home_team")  # noqa: N806
    AwayTeam = Team.__table__.alias("away_team")  # noqa: N806

    stmt = (
        select(
            Match.id,
            Match.match_date,
            Match.status,
            Match.round,
            Match.venue,
            Match.home_score,
            Match.away_score,
            HomeTeam.c.name.label("home_team"),
            HomeTeam.c.logo_url.label("home_team_logo"),
            AwayTeam.c.name.label("away_team"),
            AwayTeam.c.logo_url.label("away_team_logo"),
            Season.year.label("competition"),
        )
        .join(HomeTeam, HomeTeam.c.id == Match.home_team_id)
        .join(AwayTeam, AwayTeam.c.id == Match.away_team_id)
        .join(Season, Season.id == Match.season_id, isouter=True)
        .where(Match.id.in_(match_ids))
    )
    rows = {row.id: row for row in session.execute(stmt).all()}

    pred_stmt = (
        select(
            Prediction.match_id,
            Prediction.prob_home_win,
            Prediction.prob_draw,
            Prediction.prob_away_win,
            Prediction.confidence_score,
        )
        .where(
            Prediction.match_id.in_(match_ids),
            Prediction.model_version == settings.ACTIVE_MODEL_NAME,
        )
        .order_by(desc(Prediction.published_at))
    )
    # Keep the most-recent prediction per match (first hit wins thanks to ORDER BY).
    preds: dict[int, Any] = {}
    for row in session.execute(pred_stmt).all():
        preds.setdefault(row.match_id, row)

    out: list[MatchSummary] = []
    for mid in match_ids:
        row = rows.get(mid)
        if row is None:
            continue
        pred = preds.get(mid)
        out.append(
            MatchSummary(
                match_id=row.id,
                match_date=row.match_date,
                home_team=row.home_team,
                away_team=row.away_team,
                home_team_logo=row.home_team_logo,
                away_team_logo=row.away_team_logo,
                competition=str(row.competition) if row.competition else None,
                status=row.status,
                round=row.round,
                venue=row.venue,
                home_score=row.home_score,
                away_score=row.away_score,
                prob_home_win=float(pred.prob_home_win) if pred else None,
                prob_draw=float(pred.prob_draw) if pred else None,
                prob_away_win=float(pred.prob_away_win) if pred else None,
                confidence_score=int(pred.confidence_score) if pred else None,
            )
        )
    return out

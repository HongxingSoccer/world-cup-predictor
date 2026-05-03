"""POST /api/v1/predict — generate (and optionally publish) a prediction."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.api.dependencies import get_db_session, get_prediction_service
from src.api.schemas.predict import (
    PredictionBody,
    PredictRequest,
    PredictResponse,
    TeamBrief,
)
from src.ml.prediction_service import PredictionService
from src.models.match import Match
from src.models.team import Team

router = APIRouter(prefix="/api/v1", tags=["predict"])


@router.post("/predict", response_model=PredictResponse)
def predict_match(
    request: PredictRequest,
    db_session: Session = Depends(get_db_session),
    service: PredictionService = Depends(get_prediction_service),
) -> PredictResponse:
    """Generate a fresh prediction for `match_id`.

    Validates the match exists and isn't cancelled, then delegates to
    `PredictionService.generate_prediction`. When `publish=true` the result
    is also persisted and a Kafka event fires.
    """
    match = db_session.get(Match, request.match_id)
    if match is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"match {request.match_id} not found",
        )
    if match.status == "cancelled":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="match is cancelled — prediction declined",
        )

    full = service.generate_prediction(
        request.match_id,
        model_version=request.model_version,
        publish=request.publish,
    )

    home_team = db_session.get(Team, match.home_team_id)
    away_team = db_session.get(Team, match.away_team_id)

    body = PredictionBody(
        prob_home_win=full.prediction.prob_home_win,
        prob_draw=full.prediction.prob_draw,
        prob_away_win=full.prediction.prob_away_win,
        lambda_home=full.prediction.lambda_home,
        lambda_away=full.prediction.lambda_away,
        btts_prob=full.prediction.btts_prob,
        over_under_probs=full.prediction.over_under_probs,
        top_scores=full.prediction.top_scores,
        score_matrix=(full.prediction.score_matrix if request.include_score_matrix else None),
    )

    return PredictResponse(
        match_id=match.id,
        model_version=full.model_version,
        feature_version=full.feature_version,
        home_team=TeamBrief(
            id=match.home_team_id,
            name=home_team.name if home_team else "?",
            name_zh=home_team.name_zh if home_team else None,
        ),
        away_team=TeamBrief(
            id=match.away_team_id,
            name=away_team.name if away_team else "?",
            name_zh=away_team.name_zh if away_team else None,
        ),
        match_date=match.match_date,
        predictions=body,
        confidence_score=full.confidence.score,
        confidence_level=full.confidence.level,
        features_used=full.features_snapshot,
        prediction_id=full.prediction_id,
        content_hash=full.content_hash,
    )

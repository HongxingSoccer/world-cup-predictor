"""Pydantic v2 request / response schemas for the inference API."""
from .odds import (
    OddsAnalysisRequest,
    OddsAnalysisResponse,
    OddsMarketSummary,
    ValueSignal,
)
from .predict import (
    PredictionBody,
    PredictRequest,
    PredictResponse,
    TeamBrief,
)
from .predictions import (
    PredictionDetailResponse,
    PredictionTodayItem,
    PredictionTodayResponse,
)

__all__ = [
    "OddsAnalysisRequest",
    "OddsAnalysisResponse",
    "OddsMarketSummary",
    "PredictRequest",
    "PredictResponse",
    "PredictionBody",
    "PredictionDetailResponse",
    "PredictionTodayItem",
    "PredictionTodayResponse",
    "TeamBrief",
    "ValueSignal",
]

"""Kafka producers, payload schemas, and topic constants.

Public exports are grouped so callers can depend on a single import:

    from src.events import (
        EventProducer, build_producer,
        TOPIC_MATCH_FINISHED, MatchFinishedPayload,
    )
"""
from .producer import (
    EventEnvelope,
    EventProducer,
    NullEventProducer,
    build_producer,
)
from .schemas import (
    DataQualityAlertPayload,
    MatchCreatedPayload,
    MatchFinishedPayload,
    MatchUpdatedPayload,
    OddsUpdatedPayload,
    PredictionPublishedPayload,
    PredictionRedHitPayload,
)
from .topics import (
    ALL_TOPICS,
    TOPIC_DATA_QUALITY_ALERT,
    TOPIC_MATCH_CREATED,
    TOPIC_MATCH_FINISHED,
    TOPIC_MATCH_UPDATED,
    TOPIC_ODDS_UPDATED,
    TOPIC_PREDICTION_PUBLISHED,
    TOPIC_PREDICTION_RED_HIT,
)

__all__ = [
    "ALL_TOPICS",
    "DataQualityAlertPayload",
    "EventEnvelope",
    "EventProducer",
    "MatchCreatedPayload",
    "MatchFinishedPayload",
    "MatchUpdatedPayload",
    "NullEventProducer",
    "OddsUpdatedPayload",
    "PredictionPublishedPayload",
    "PredictionRedHitPayload",
    "TOPIC_DATA_QUALITY_ALERT",
    "TOPIC_MATCH_CREATED",
    "TOPIC_MATCH_FINISHED",
    "TOPIC_MATCH_UPDATED",
    "TOPIC_ODDS_UPDATED",
    "TOPIC_PREDICTION_PUBLISHED",
    "TOPIC_PREDICTION_RED_HIT",
    "build_producer",
]

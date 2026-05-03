"""Kafka topic names — kept in one file to avoid drift between producers/consumers.

Naming convention: ``{aggregate}.{verb}`` so the topic itself is the
``event_type`` field on the envelope (see `producer.EventEnvelope`).
"""
from __future__ import annotations

from typing import Final

# Match-domain events.
TOPIC_MATCH_CREATED: Final[str] = "match.created"
TOPIC_MATCH_UPDATED: Final[str] = "match.updated"
TOPIC_MATCH_FINISHED: Final[str] = "match.finished"

# Odds-domain events (single topic — the payload carries market type).
TOPIC_ODDS_UPDATED: Final[str] = "odds.updated"

# Phase-2 ML output: a fresh prediction has been written to `predictions`.
TOPIC_PREDICTION_PUBLISHED: Final[str] = "prediction.published"

# Phase-3 settlement: published when a prediction's 1x2 pick was correct
# — drives the social-share fan-out.
TOPIC_PREDICTION_RED_HIT: Final[str] = "prediction.red_hit"

# Operational / data-quality alerts.
TOPIC_DATA_QUALITY_ALERT: Final[str] = "data.quality.alert"

# All known topics (used by infra for auto-create / ACL bootstrapping).
ALL_TOPICS: Final[tuple[str, ...]] = (
    TOPIC_MATCH_CREATED,
    TOPIC_MATCH_UPDATED,
    TOPIC_MATCH_FINISHED,
    TOPIC_ODDS_UPDATED,
    TOPIC_PREDICTION_PUBLISHED,
    TOPIC_PREDICTION_RED_HIT,
    TOPIC_DATA_QUALITY_ALERT,
)

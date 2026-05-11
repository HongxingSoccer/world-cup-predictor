"""Kafka event producer.

Every event published by the platform flows through this module and is wrapped
in a uniform `EventEnvelope`:

    {
      "event_type": "match.finished",
      "event_id":   "<uuid4>",
      "timestamp":  "<ISO 8601 UTC>",
      "source":     "ingestion-service",
      "payload":    { ... domain-specific ... }
    }

Topic == event_type (kept in `topics.py`), so consumers wire one consumer per
topic and trust both the topic name and the envelope's `event_type` field.

A `NullEventProducer` is provided for unit tests and for local runs where
running a full Kafka broker is overkill.
"""
from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any, Protocol

import structlog
from kafka import KafkaProducer
from pydantic import BaseModel, ConfigDict, Field

from src.config.kafka_config import producer_config

logger = structlog.get_logger(__name__)


class EventEnvelope(BaseModel):
    """Uniform wrapper for every published event."""

    model_config = ConfigDict(frozen=True)

    event_type: str = Field(description="Kafka topic + business event name (e.g. 'match.finished').")
    event_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    source: str = Field(description="Service that emitted the event (e.g. 'ingestion-service').")
    payload: dict[str, Any]


class EventProducer(Protocol):
    """Contract every pipeline / task uses to emit events."""

    def publish(
        self,
        *,
        event_type: str,
        key: str,
        payload: BaseModel | dict[str, Any],
        source: str = ...,
    ) -> None: ...

    def close(self) -> None: ...


class _DefaultProducer:
    """Production producer backed by `kafka-python` and the `EventEnvelope`."""

    def __init__(self, *, default_source: str) -> None:
        self._default_source = default_source
        self._producer = KafkaProducer(
            value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
            key_serializer=lambda k: k.encode("utf-8") if isinstance(k, str) else k,
            **producer_config(client_id_suffix=default_source),
        )
        self._log = logger.bind(component="event_producer")

    def publish(
        self,
        *,
        event_type: str,
        key: str,
        payload: BaseModel | dict[str, Any],
        source: str | None = None,
    ) -> None:
        envelope = EventEnvelope(
            event_type=event_type,
            source=source or self._default_source,
            payload=_to_dict(payload),
        )
        # Topic name == event_type by convention.
        future = self._producer.send(
            event_type, key=key, value=envelope.model_dump(mode="json")
        )
        try:
            future.get(timeout=10)
        except Exception as exc:
            self._log.error(
                "event_publish_failed",
                event_type=event_type,
                key=key,
                error=str(exc),
            )
            raise

    def close(self) -> None:
        self._producer.flush()
        self._producer.close()


class NullEventProducer:
    """No-op producer for tests / disabled-Kafka runs."""

    def publish(
        self,
        *,
        event_type: str,
        key: str,
        payload: BaseModel | dict[str, Any],
        source: str = "ingestion-service",
    ) -> None:
        logger.debug(
            "event_publish_noop",
            event_type=event_type,
            key=key,
            source=source,
            payload_keys=list(_to_dict(payload).keys()),
        )

    def close(self) -> None:
        return None


def build_producer(
    *,
    enabled: bool = True,
    default_source: str = "ingestion-service",
) -> EventProducer:
    """Factory used by application wiring.

    Args:
        enabled: When False, returns a `NullEventProducer`. Useful for local
            dev runs and tests that don't spin up a broker.
        default_source: Value used for `EventEnvelope.source` when callers
            don't pass an explicit `source=` to `publish()`.

    Returns:
        Anything implementing the `EventProducer` protocol.
    """
    if not enabled:
        return NullEventProducer()
    return _DefaultProducer(default_source=default_source)


def _to_dict(payload: BaseModel | dict[str, Any]) -> dict[str, Any]:
    """Coerce a payload into a JSON-friendly dict."""
    if isinstance(payload, BaseModel):
        return payload.model_dump(mode="json")
    return dict(payload)

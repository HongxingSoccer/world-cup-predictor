"""Kafka client configuration shared by the producer and (future) consumers.

Producers / consumers should call `producer_config()` or `consumer_config(group_id)`
rather than constructing their own dict — that way settings (broker list,
client ids, security) live in one place and consumers can be added later
without re-deriving conventions.

Only producer settings are used in Phase 1 (`src.events.producer`); the
consumer helper is included so Phase 2 services can subscribe to topics
without duplicating boilerplate.
"""
from __future__ import annotations

from typing import Any

from src.config.settings import settings

# Stable client identifier prefix — Kafka uses it for connection metrics and
# auth audit. Worker-side concerns (instance number, pod name) get suffixed
# at runtime via `client_id_suffix`.
CLIENT_ID_PREFIX: str = "wcp-ingestion"

# Producer defaults: at-least-once durability with modest batching latency.
# `acks=all` waits for every in-sync replica before returning, which is the
# Phase-1 stance — we'd rather pause ingest than silently drop events.
_PRODUCER_DEFAULTS: dict[str, Any] = {
    "acks": "all",
    "linger_ms": 50,
    "retries": 5,
    "max_in_flight_requests_per_connection": 5,
    "compression_type": "lz4",
}

# Consumer defaults: read-from-earliest the first time a group connects so
# back-fills don't lose history; subsequent runs resume from committed offset.
_CONSUMER_DEFAULTS: dict[str, Any] = {
    "auto_offset_reset": "earliest",
    "enable_auto_commit": False,  # commit explicitly after handler success
    "max_poll_records": 100,
    "session_timeout_ms": 30_000,
}


def bootstrap_servers() -> list[str]:
    """Return the resolved bootstrap-server list (already split in settings)."""
    return list(settings.KAFKA_BROKERS)


def producer_config(*, client_id_suffix: str = "producer") -> dict[str, Any]:
    """Return a kafka-python `KafkaProducer(**kwargs)` config dict.

    Args:
        client_id_suffix: Appended to `CLIENT_ID_PREFIX` to form `client_id`.
            Use a per-process value (e.g. ``f"worker-{hostname}"``) so broker
            metrics distinguish individual processes.
    """
    return {
        "bootstrap_servers": bootstrap_servers(),
        "client_id": f"{CLIENT_ID_PREFIX}-{client_id_suffix}",
        **_PRODUCER_DEFAULTS,
    }


def consumer_config(group_id: str, *, client_id_suffix: str = "consumer") -> dict[str, Any]:
    """Return a kafka-python `KafkaConsumer(**kwargs)` config dict.

    Args:
        group_id: Consumer-group id (drives partition assignment + offset
            commit isolation across services).
        client_id_suffix: Per-process tag, same purpose as in `producer_config`.
    """
    return {
        "bootstrap_servers": bootstrap_servers(),
        "client_id": f"{CLIENT_ID_PREFIX}-{client_id_suffix}",
        "group_id": group_id,
        **_CONSUMER_DEFAULTS,
    }

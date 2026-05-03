"""Celery tasks for share-card rendering.

Three families of tasks:

    1. Per-platform render tasks (`card.render_prediction` / `render_red_hit` /
       `render_track_record`). Each writes one row to `share_cards`.

    2. Fan-out helpers (`generate_prediction_cards` / `generate_red_hit_cards`)
       that enqueue the four platform variants in parallel. These are the
       entry points called by the prediction-publish + settlement code paths.

Fan-out targets are intentionally separate tasks so a Playwright crash on
one platform doesn't poison the others — Celery retries the failed one in
isolation.
"""
from __future__ import annotations

from typing import Any

import structlog

from src.config.celery_config import (
    DEFAULT_MAX_RETRIES,
    DEFAULT_RETRY_BACKOFF,
    DEFAULT_RETRY_BACKOFF_MAX,
    app,
)
from src.content.card_generator import ALL_PLATFORMS, CardGenerator
from src.utils.db import session_scope

logger = structlog.get_logger(__name__)

# How many times to attempt a card render before giving up.
RENDER_MAX_RETRIES: int = DEFAULT_MAX_RETRIES


# --- Per-platform render tasks -------------------------------------------


@app.task(
    bind=True,
    name="card.render_prediction",
    max_retries=RENDER_MAX_RETRIES,
    retry_backoff=DEFAULT_RETRY_BACKOFF,
    retry_backoff_max=DEFAULT_RETRY_BACKOFF_MAX,
)
def render_prediction_card(self, prediction_id: int, platform: str) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    try:
        with session_scope() as session:
            url = CardGenerator(session).generate_prediction_card(int(prediction_id), platform)
        return {"prediction_id": prediction_id, "platform": platform, "url": url}
    except Exception as exc:
        logger.exception("card_render_prediction_failed", prediction_id=prediction_id, platform=platform)
        raise self.retry(exc=exc) from exc


@app.task(
    bind=True,
    name="card.render_red_hit",
    max_retries=RENDER_MAX_RETRIES,
    retry_backoff=DEFAULT_RETRY_BACKOFF,
    retry_backoff_max=DEFAULT_RETRY_BACKOFF_MAX,
)
def render_red_hit_card(self, prediction_result_id: int, platform: str) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    try:
        with session_scope() as session:
            url = CardGenerator(session).generate_red_hit_card(int(prediction_result_id), platform)
        return {"prediction_result_id": prediction_result_id, "platform": platform, "url": url}
    except Exception as exc:
        logger.exception("card_render_red_hit_failed", prediction_result_id=prediction_result_id, platform=platform)
        raise self.retry(exc=exc) from exc


@app.task(
    bind=True,
    name="card.render_track_record",
    max_retries=RENDER_MAX_RETRIES,
    retry_backoff=DEFAULT_RETRY_BACKOFF,
    retry_backoff_max=DEFAULT_RETRY_BACKOFF_MAX,
)
def render_track_record_card(self, platform: str, period: str = "all_time") -> dict[str, Any]:  # type: ignore[no-untyped-def]
    try:
        with session_scope() as session:
            url = CardGenerator(session).generate_track_record_card(platform, period=period)
        return {"platform": platform, "period": period, "url": url}
    except Exception as exc:
        logger.exception("card_render_track_record_failed", platform=platform, period=period)
        raise self.retry(exc=exc) from exc


# --- Fan-out wrappers ----------------------------------------------------


@app.task(name="card.fanout_prediction")
def generate_prediction_cards(prediction_id: int) -> dict[str, Any]:
    """Enqueue per-platform card renders for a freshly-published prediction."""
    enqueued = 0
    for platform in ALL_PLATFORMS:
        app.send_task("card.render_prediction", args=[int(prediction_id), platform])
        enqueued += 1
    logger.info("card_fanout_prediction", prediction_id=prediction_id, platforms=enqueued)
    return {"prediction_id": prediction_id, "platforms": list(ALL_PLATFORMS), "enqueued": enqueued}


@app.task(name="card.fanout_red_hit")
def generate_red_hit_cards(prediction_result_id: int) -> dict[str, Any]:
    """Enqueue per-platform red-hit cards after settlement detects a winning 1x2."""
    enqueued = 0
    for platform in ALL_PLATFORMS:
        app.send_task("card.render_red_hit", args=[int(prediction_result_id), platform])
        enqueued += 1
    logger.info("card_fanout_red_hit", prediction_result_id=prediction_result_id, platforms=enqueued)
    return {
        "prediction_result_id": prediction_result_id,
        "platforms": list(ALL_PLATFORMS),
        "enqueued": enqueued,
    }

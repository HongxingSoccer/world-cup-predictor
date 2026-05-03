"""Structured logging setup.

A single `configure_logging()` call wires structlog to render JSON to stdout
(or human-readable for local dev), so every module can simply do
`structlog.get_logger(__name__)` and emit key=value events.

Importing this module is *not* enough — call `configure_logging()` once on
process start (FastAPI startup, Celery init, CLI entry-point).
"""
from __future__ import annotations

import logging
import sys
from typing import Any

import structlog
from structlog.types import EventDict, Processor

from src.config.settings import settings


def _drop_color_message_key(_: Any, __: Any, event_dict: EventDict) -> EventDict:
    """Remove uvicorn's `color_message` duplicate of `event` for cleaner output."""
    event_dict.pop("color_message", None)
    return event_dict


def configure_logging(*, json_logs: bool = True) -> None:
    """Configure structlog + stdlib logging for the whole process.

    Args:
        json_logs: If True, emit JSON one-line records (for prod / log shippers).
            If False, render colorized key=value lines (for local dev).
    """
    log_level = getattr(logging, settings.LOG_LEVEL, logging.INFO)

    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        _drop_color_message_key,
    ]

    renderer: Processor = (
        structlog.processors.JSONRenderer()
        if json_logs
        else structlog.dev.ConsoleRenderer(colors=True)
    )

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(log_level)
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(log_level)

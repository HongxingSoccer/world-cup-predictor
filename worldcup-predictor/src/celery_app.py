"""Celery worker entrypoint.

Importing this module triggers two things in order:

    1. Loads the configured Celery `app` from `src.config.celery_config`.
    2. Imports `src.tasks` so every `@app.task` decorator runs and registers
       its task in the global registry.

Workers / beat are started via:

    celery -A src.celery_app worker --loglevel=INFO
    celery -A src.celery_app beat   --loglevel=INFO

Pointing at this thin re-export module (rather than the config module
directly) ensures the task registry is fully populated before the worker
starts consuming, which avoids "Received unregistered task" errors on the
first message.
"""
from __future__ import annotations

from src.config.celery_config import app

# Side-effect import — registers every @app.task in src/tasks/*.
# Marked noqa because flake8 / ruff would otherwise flag the unused import.
import src.tasks  # noqa: F401, E402

__all__ = ["app"]

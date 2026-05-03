"""FastAPI inference service (Phase 2).

Exports `app` so production runners can `uvicorn src.api:app` without the
extra `.main` suffix.
"""
from .main import app

__all__ = ["app"]

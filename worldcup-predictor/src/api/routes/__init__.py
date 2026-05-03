"""API route modules. Each file exposes a `router` to be mounted by `main.py`."""
from . import health, odds, predict, predictions

__all__ = ["health", "odds", "predict", "predictions"]

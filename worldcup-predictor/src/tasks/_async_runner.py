"""Bridge between synchronous Celery task bodies and async pipeline code.

`run_async(coro)` simply calls `asyncio.run(coro)`. The wrapper exists so the
import surface inside task modules stays uniform (and so we have a single
chokepoint if we ever switch to a long-lived event loop per worker).
"""
from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from typing import Any, TypeVar

T = TypeVar("T")


def run_async(coro: Coroutine[Any, Any, T]) -> T:
    """Run an async coroutine to completion from sync Celery code."""
    return asyncio.run(coro)

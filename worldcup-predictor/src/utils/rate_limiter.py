"""Token-bucket rate limiter for outbound HTTP traffic.

Each `BaseDataSourceAdapter` owns a `RateLimiter` configured with that
provider's per-second budget. Calls to `acquire()` block (asynchronously) until
a token is available, and add a small randomized jitter to avoid thundering-herd
patterns when many tasks fire on the same scheduler tick.
"""
from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass
from time import monotonic


@dataclass(frozen=True)
class RateLimitConfig:
    """Configuration for a `RateLimiter` instance.

    Attributes:
        requests_per_second: Steady-state request budget.
        burst_size: Max tokens the bucket can hold; allows short bursts above
            the steady-state rate before throttling kicks in.
    """

    requests_per_second: float
    burst_size: int


class RateLimiter:
    """Async token-bucket limiter with randomized inter-request jitter.

    The bucket refills continuously at `requests_per_second` and is capped at
    `burst_size` tokens. After each successful `acquire()` the caller sleeps an
    extra random 0.5–2.0 s to mimic human-like pacing, which materially reduces
    bot-detection signals on scraping targets.

    Attributes:
        JITTER_MIN_SECONDS: Lower bound of the post-acquire jitter window.
        JITTER_MAX_SECONDS: Upper bound of the post-acquire jitter window.
    """

    JITTER_MIN_SECONDS: float = 0.5
    JITTER_MAX_SECONDS: float = 2.0

    def __init__(self, config: RateLimitConfig) -> None:
        if config.requests_per_second <= 0:
            raise ValueError("requests_per_second must be > 0")
        if config.burst_size <= 0:
            raise ValueError("burst_size must be > 0")

        self._config = config
        self._tokens: float = float(config.burst_size)
        self._last_refill: float = monotonic()
        self._lock = asyncio.Lock()

    # --- Public methods ---

    async def acquire(self, *, jitter: bool = True) -> None:
        """Block until one token is available, then optionally sleep a jitter.

        Args:
            jitter: When True (default), sleep a uniform random
                [JITTER_MIN_SECONDS, JITTER_MAX_SECONDS] seconds after
                consuming the token.
        """
        async with self._lock:
            await self._wait_for_token()
            self._tokens -= 1.0

        if jitter:
            await asyncio.sleep(
                random.uniform(self.JITTER_MIN_SECONDS, self.JITTER_MAX_SECONDS)
            )

    # --- Private methods ---

    async def _wait_for_token(self) -> None:
        """Refill, then sleep until at least one token is available."""
        self._refill()
        while self._tokens < 1.0:
            deficit = 1.0 - self._tokens
            wait_seconds = deficit / self._config.requests_per_second
            await asyncio.sleep(wait_seconds)
            self._refill()

    def _refill(self) -> None:
        now = monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(
            float(self._config.burst_size),
            self._tokens + elapsed * self._config.requests_per_second,
        )
        self._last_refill = now

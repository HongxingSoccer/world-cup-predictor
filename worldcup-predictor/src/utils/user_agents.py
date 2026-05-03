"""User-agent rotation pool for scraper traffic.

Re-using the same UA across thousands of requests is a strong bot signal.
Scrapers (FBref, Transfermarkt, OddsPortal) call `random_user_agent()` per
request; API adapters (API-Football, Odds-API) keep the static UA configured
on the `httpx.AsyncClient`.

Refresh quarterly: keep entries roughly aligned with the current major versions
of Chrome / Firefox / Safari. Outdated UA strings are themselves a fingerprint.
"""
from __future__ import annotations

import random
from typing import Final

USER_AGENTS: Final[tuple[str, ...]] = (
    # Chrome / Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    # Chrome / macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    # Firefox / Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    # Firefox / macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.2; rv:121.0) Gecko/20100101 Firefox/121.0",
    # Safari / macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    # Edge / Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
)


def random_user_agent() -> str:
    """Return a uniformly random UA string from `USER_AGENTS`."""
    return random.choice(USER_AGENTS)

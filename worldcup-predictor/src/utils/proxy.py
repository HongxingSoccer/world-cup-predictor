"""Proxy-pool client for scraper traffic.

The pool service (Squid frontends, commercial pools, or our own rotating
service) is expected to expose a single endpoint that returns one usable
proxy URL on each GET (e.g. ``http://user:pass@host:port``). When
`PROXY_POOL_URL` is unset, `ProxyPool.get()` returns ``None`` and the caller
runs without a proxy.

The pool is intentionally lazy: it owns no persistent client and makes one
short HTTP call per `get()` invocation. Scrapers call it on bootstrap and
again whenever a 403 forces a rotation.
"""
from __future__ import annotations

import httpx
import structlog

from src.config.settings import settings

logger = structlog.get_logger(__name__)


class ProxyPool:
    """Fetches usable proxy URLs from the configured pool endpoint.

    Attributes:
        FETCH_TIMEOUT_SECONDS: Hard timeout for the pool request itself.
            Kept low so a slow pool doesn't stall the scraper indefinitely.
    """

    FETCH_TIMEOUT_SECONDS: float = 5.0

    def __init__(self, pool_url: str | None = None) -> None:
        self._pool_url = pool_url if pool_url is not None else settings.PROXY_POOL_URL

    async def get(self) -> str | None:
        """Return a fresh proxy URL or None if the pool is unconfigured / failed.

        Errors are logged but never raised: a missing proxy degrades to direct
        traffic, which is recoverable; raising would abort the scraping run.
        """
        if not self._pool_url:
            return None
        try:
            async with httpx.AsyncClient(timeout=self.FETCH_TIMEOUT_SECONDS) as client:
                response = await client.get(self._pool_url)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("proxy_pool_fetch_failed", url=self._pool_url, error=str(exc))
            return None

        proxy = response.text.strip()
        return proxy or None

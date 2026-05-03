"""OddsPortal historical-odds scraper (Playwright-driven, Phase 1 skeleton).

OddsPortal pages are JS-rendered behind a Cloudflare challenge, so requests-
based scraping doesn't work — we need a real browser. This module sets up a
managed Playwright Chromium instance and exposes the lifecycle. Page parsing
is a Phase 2 deliverable; the methods below raise `AdapterMethodNotSupported`
or return empty results until then.

Usage:

    async with OddsPortalAdapter() as adapter:
        await adapter.ensure_browser()
        # TODO(Phase 2): adapter.fetch_historical_odds(match_url, ...)

Why we still want this in Phase 1 codebase:
    - Locks in the contract (`BaseDataSourceAdapter`) so the audit log and
      pipeline plumbing already work.
    - Lets ops smoke-test browser launch / proxy wiring before page parsing
      lands.
"""
from __future__ import annotations

from typing import Any

import structlog

from src.adapters.base import (
    AdapterMethodNotSupported,
    BaseDataSourceAdapter,
    DataFetchError,
)
from src.dto.match import MatchDTO
from src.dto.odds import OddsDTO
from src.dto.player import PlayerStatDTO
from src.dto.stats import MatchDetailDTO, TeamStatsDTO
from src.utils.proxy import ProxyPool
from src.utils.rate_limiter import RateLimitConfig
from src.utils.user_agents import random_user_agent

logger = structlog.get_logger(__name__)

ODDS_PORTAL_BASE_URL: str = "https://www.oddsportal.com"
SOURCE_NAME: str = "odds_portal"


class OddsPortalAdapter(BaseDataSourceAdapter):
    """Skeleton adapter for OddsPortal historical odds.

    Owns its own Chromium instance via `playwright.async_api`; the browser is
    launched lazily on first use and torn down in `aclose()`.

    .. note::
        Requires ``playwright install chromium`` before first run.
    """

    DEFAULT_RATE_LIMIT: RateLimitConfig = RateLimitConfig(
        requests_per_second=1 / 5,  # 1 page-load / 5 s
        burst_size=1,
    )

    def __init__(
        self,
        *,
        base_url: str = ODDS_PORTAL_BASE_URL,
        rate_limit: RateLimitConfig | None = None,
        proxy_pool: ProxyPool | None = None,
        headless: bool = True,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            SOURCE_NAME,
            rate_limit=rate_limit or self.DEFAULT_RATE_LIMIT,
            base_url=base_url,
            **kwargs,
        )
        self._proxy_pool = proxy_pool or ProxyPool()
        self._headless = headless
        self._retryable_status = self._retryable_status | {403}

        # Playwright handles — populated by ensure_browser().
        self._playwright: Any | None = None
        self._browser: Any | None = None
        self._context: Any | None = None

    # --- Lifecycle ---

    async def ensure_browser(self) -> None:
        """Launch Chromium + a context with a fresh UA. Idempotent."""
        if self._browser is not None:
            return
        try:
            from playwright.async_api import async_playwright  # local: optional dep
        except ImportError as exc:
            raise DataFetchError(
                SOURCE_NAME,
                "playwright is not installed; run `pip install playwright && playwright install chromium`",
            ) from exc

        proxy = await self._proxy_pool.get()
        self._playwright = await async_playwright().start()
        launch_args: dict[str, Any] = {"headless": self._headless}
        if proxy:
            launch_args["proxy"] = {"server": proxy}
        self._browser = await self._playwright.chromium.launch(**launch_args)
        self._context = await self._browser.new_context(user_agent=random_user_agent())
        self._log.info("oddsportal_browser_ready", proxy=bool(proxy))

    async def aclose(self) -> None:
        if self._context is not None:
            await self._context.close()
            self._context = None
        if self._browser is not None:
            await self._browser.close()
            self._browser = None
        if self._playwright is not None:
            await self._playwright.stop()
            self._playwright = None
        await super().aclose()

    # --- BaseDataSourceAdapter required methods ---

    def get_rate_limit(self) -> RateLimitConfig:
        return self.DEFAULT_RATE_LIMIT

    async def health_check(self) -> bool:
        # Skip Playwright for the smoke test — just confirm the homepage HTML
        # responds. Full browser readiness is tested in integration suites.
        try:
            response = await self._request_with_retry("/", max_retries=1)
        except DataFetchError:
            return False
        return response.status_code == 200

    async def fetch_matches(self, season_id: str | int) -> list[MatchDTO]:
        # TODO(Phase 2): scrape `/matches/soccer/{date}/` archive pages.
        raise AdapterMethodNotSupported(
            "OddsPortalAdapter.fetch_matches deferred to Phase 2 (Playwright parser)"
        )

    async def fetch_match_detail(self, match_id: str | int) -> MatchDetailDTO:
        # TODO(Phase 2): navigate to `match_url`, dismiss cookie banner,
        # iterate market tabs (1x2 / OU / AH), collect bookmaker rows.
        raise AdapterMethodNotSupported(
            "OddsPortalAdapter.fetch_match_detail deferred to Phase 2 (Playwright parser)"
        )

    async def fetch_team_stats(
        self, team_id: str | int, season_id: str | int
    ) -> TeamStatsDTO:
        raise AdapterMethodNotSupported("OddsPortalAdapter does not provide team stats")

    async def fetch_player_stats(self, match_id: str | int) -> list[PlayerStatDTO]:
        raise AdapterMethodNotSupported("OddsPortalAdapter does not provide player stats")

    # --- Skeleton helpers (filled out in Phase 2) ---

    async def fetch_historical_odds(self, match_url: str) -> list[OddsDTO]:
        """Scrape every market on a single OddsPortal match page.

        Phase 1 status: stubbed. Real implementation needs:
            1. ``self.ensure_browser()`` then open `match_url`.
            2. Wait for `.table-container` to be visible (Cloudflare challenge
               can briefly hide it on first load).
            3. Click through each market tab (`#tab-mod-1x2`, `#tab-mod-ou`,
               `#tab-mod-ah`) and collect rendered HTML.
            4. Pass each market's HTML into a parser → ``OddsDTO`` mapper.
        """
        # TODO(Phase 2): implement steps 1-4 above.
        await self.ensure_browser()
        self._log.warning("oddsportal_fetch_historical_odds_stub", url=match_url)
        return []

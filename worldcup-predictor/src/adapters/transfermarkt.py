"""Transfermarkt scraper adapter (player valuations + injuries).

Transfermarkt's market-value timeline is exposed via an undocumented JSON
endpoint (``/ceapi/marketValueDevelopment/graph/{player_id}``) which is much
nicer than parsing the chart HTML. Injuries and player profiles still come
from rendered HTML.

This adapter focuses on the three signals the data foundation needs:
    - `fetch_valuations(player_id)` → list[ValuationDTO]
    - `fetch_injuries(team_id)` → list[InjuryDTO]
    - `fetch_player_profile(player_id)` → PlayerDTO

The abstract `fetch_matches` / `fetch_match_detail` / `fetch_team_stats` /
`fetch_player_stats` methods raise `AdapterMethodNotSupported` because
Transfermarkt isn't a fixtures or stats provider.

Like FBref, the scraper rotates UAs per request and treats 403 as a "swap
proxy and retry" condition.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timezone
from typing import Any

import httpx
import structlog
from bs4 import BeautifulSoup, Tag

from src.adapters.base import (
    AdapterMethodNotSupported,
    BaseDataSourceAdapter,
    DataFetchError,
)
from src.dto.match import MatchDTO
from src.dto.player import InjuryDTO, PlayerDTO, PlayerStatDTO, ValuationDTO
from src.dto.stats import MatchDetailDTO, TeamStatsDTO
from src.utils.proxy import ProxyPool
from src.utils.rate_limiter import RateLimitConfig
from src.utils.user_agents import random_user_agent

logger = structlog.get_logger(__name__)

TRANSFERMARKT_BASE_URL: str = "https://www.transfermarkt.com"
SOURCE_NAME: str = "transfermarkt"


class TransfermarktAdapter(BaseDataSourceAdapter):
    """Scraper adapter for Transfermarkt player and team pages."""

    DEFAULT_RATE_LIMIT: RateLimitConfig = RateLimitConfig(
        requests_per_second=1 / 3,  # 1 req / 3 s
        burst_size=1,
    )

    def __init__(
        self,
        *,
        base_url: str = TRANSFERMARKT_BASE_URL,
        rate_limit: RateLimitConfig | None = None,
        proxy_pool: ProxyPool | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            SOURCE_NAME,
            rate_limit=rate_limit or self.DEFAULT_RATE_LIMIT,
            base_url=base_url,
            default_headers={
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "en-US,en;q=0.9",
            },
            **kwargs,
        )
        self._proxy_pool = proxy_pool or ProxyPool()
        self._retryable_status = self._retryable_status | {403}

    # --- Public API (Transfermarkt-specific) ---

    async def fetch_valuations(self, player_id: str | int) -> list[ValuationDTO]:
        """Return the full market-value timeline for a player."""
        path = f"/ceapi/marketValueDevelopment/graph/{int(player_id)}"
        response = await self._request_with_retry(path)
        body = response.json()
        out: list[ValuationDTO] = []
        for point in body.get("list") or []:
            try:
                out.append(self._point_to_valuation(point, player_id=str(player_id)))
            except (KeyError, ValueError) as exc:
                self._log.warning("tm_valuation_skipped", error=str(exc), point=point)
        return out

    async def fetch_injuries(self, team_id: str | int) -> list[InjuryDTO]:
        """Parse a club's injury page (HTML)."""
        # Transfermarkt URLs include a slug; passing just the id 302-redirects
        # to the canonical URL, which the AsyncClient follows.
        path = f"/_/sperrenundverletzungen/verein/{int(team_id)}"
        soup = await self._fetch_soup(path)
        return list(self._parse_injuries(soup, team_id=str(team_id)))

    async def fetch_player_profile(self, player_id: str | int) -> PlayerDTO:
        path = f"/_/profil/spieler/{int(player_id)}"
        soup = await self._fetch_soup(path)
        return self._parse_player_profile(soup, player_id=str(player_id))

    # --- BaseDataSourceAdapter required methods ---

    def get_rate_limit(self) -> RateLimitConfig:
        return self.DEFAULT_RATE_LIMIT

    async def health_check(self) -> bool:
        try:
            response = await self._request_with_retry("/", max_retries=1)
        except DataFetchError:
            return False
        return response.status_code == 200

    async def fetch_matches(self, season_id: str | int) -> list[MatchDTO]:
        raise AdapterMethodNotSupported(
            "TransfermarktAdapter does not expose fixtures (use ApiFootball / Static)"
        )

    async def fetch_match_detail(self, match_id: str | int) -> MatchDetailDTO:
        raise AdapterMethodNotSupported(
            "TransfermarktAdapter does not expose per-match detail"
        )

    async def fetch_team_stats(
        self, team_id: str | int, season_id: str | int
    ) -> TeamStatsDTO:
        raise AdapterMethodNotSupported(
            "TransfermarktAdapter does not expose match-aggregate team stats"
        )

    async def fetch_player_stats(self, match_id: str | int) -> list[PlayerStatDTO]:
        raise AdapterMethodNotSupported(
            "TransfermarktAdapter does not expose per-match player stats"
        )

    # --- Hooks ---

    def _get_extra_headers(self) -> dict[str, str]:
        return {"User-Agent": random_user_agent()}

    async def _on_blocked(self, response: httpx.Response) -> None:
        proxy = await self._proxy_pool.get()
        if proxy is None:
            self._log.error("tm_blocked_no_proxy", url=str(response.request.url))
            return
        await self._client.aclose()
        self._client = httpx.AsyncClient(
            base_url=str(self._client.base_url),
            timeout=self._client.timeout,
            proxy=proxy,
        )
        self._log.warning("tm_proxy_swapped")

    # --- Internal: HTTP / parsers ---

    async def _fetch_soup(self, path: str) -> BeautifulSoup:
        response = await self._request_with_retry(path)
        return BeautifulSoup(response.text, "lxml")

    @staticmethod
    def _point_to_valuation(point: dict[str, Any], *, player_id: str) -> ValuationDTO:
        # Transfermarkt's graph endpoint returns timestamps in milliseconds and
        # values in EUR (already in whole euros).
        ts_ms = int(point["datum_mw"])
        captured = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
        return ValuationDTO(
            player_external_id=player_id,
            team_external_id=str(point.get("verein")) if point.get("verein") else None,
            value_date=captured.date(),
            market_value_eur=int(point["mw"]),
            captured_at=captured,
        )

    def _parse_injuries(self, soup: BeautifulSoup, *, team_id: str) -> list[InjuryDTO]:
        # The injury table sits inside `<div class="responsive-table">` with a
        # canonical column order: name | injury | from | until | duration | games missed.
        out: list[InjuryDTO] = []
        table = soup.find("table", class_="items")
        if not isinstance(table, Tag):
            return out

        for row in table.find_all("tr"):
            if not isinstance(row, Tag):
                continue
            cells = row.find_all("td")
            if len(cells) < 5:
                continue
            player_link = row.find("a", href=re.compile(r"/profil/spieler/"))
            if not isinstance(player_link, Tag):
                continue
            player_id = _player_id_from_href(player_link["href"])
            if player_id is None:
                continue
            try:
                injury = InjuryDTO(
                    player_external_id=player_id,
                    team_external_id=team_id,
                    injury_type=_text(cells[1]),
                    severity=None,
                    start_date=_parse_tm_date(_text(cells[2])),
                    expected_return=_safe_parse_tm_date(_text(cells[3])),
                    actual_return=None,
                    is_active=True,
                )
            except ValueError as exc:
                self._log.warning("tm_injury_skipped", error=str(exc))
                continue
            out.append(injury)
        return out

    def _parse_player_profile(self, soup: BeautifulSoup, *, player_id: str) -> PlayerDTO:
        name_node = soup.find("h1", class_="data-header__headline-wrapper")
        if not isinstance(name_node, Tag):
            raise DataFetchError(SOURCE_NAME, f"name not found on player {player_id}")
        # `<h1>... Lionel Messi</h1>` — drop jersey number / extra spans.
        name = " ".join(part for part in name_node.stripped_strings if not part.startswith("#"))
        # TODO(Phase 2): nationality / DOB / position — Transfermarkt encodes
        # them in a sibling `<ul class="data-header__items">` with locale-
        # dependent labels. Phase 1 ingest only needs the canonical name and
        # external id; richer fields can land via API-Football too.
        return PlayerDTO(
            external_id=player_id,
            name=name,
            nationality=None,
            date_of_birth=None,
            position=None,
            current_team_external_id=None,
            national_team_external_id=None,
            market_value_eur=None,
            photo_url=None,
        )


# --- Module-level parser helpers ---


def _text(node: Any) -> str:
    if isinstance(node, Tag):
        return node.get_text(" ", strip=True)
    return str(node or "").strip()


def _player_id_from_href(href: str) -> str | None:
    # `/firstname-lastname/profil/spieler/123456`
    match = re.search(r"/profil/spieler/(\d+)", href)
    return match.group(1) if match else None


def _parse_tm_date(raw: str) -> date:
    # Transfermarkt date format: "Aug 1, 2024" (English locale only — caller is
    # expected to set Accept-Language: en-US on the request).
    return datetime.strptime(raw, "%b %d, %Y").date()


def _safe_parse_tm_date(raw: str) -> date | None:
    if not raw or raw == "?":
        return None
    try:
        return _parse_tm_date(raw)
    except ValueError:
        return None

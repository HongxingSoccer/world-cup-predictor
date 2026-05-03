"""FBref HTML-scrape adapter (advanced stats: xG, xA, shots, passing).

FBref blocks high-volume traffic, so the rate limit is set to one request
every three seconds and the User-Agent is rotated per request. The 403
response (which is what FBref returns when a client trips its bot detection)
is treated as a retryable status and triggers a proxy swap via `_on_blocked`.

Match URL: ``/en/matches/{8-char-hex}/`` — page contains team-level summary
tables, head-to-head info, shots logs, and per-player stat grids. Only the
team summary and per-player grids are parsed here; the rest is left as
`# TODO(Phase 2)` markers.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
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
from src.dto.player import PlayerStatDTO
from src.dto.stats import MatchDetailDTO, MatchStatsDTO, TeamStatsDTO
from src.utils.proxy import ProxyPool
from src.utils.rate_limiter import RateLimitConfig
from src.utils.user_agents import random_user_agent

logger = structlog.get_logger(__name__)

FBREF_BASE_URL: str = "https://fbref.com"
SOURCE_NAME: str = "fbref"


class FBrefAdapter(BaseDataSourceAdapter):
    """Scrape adapter for FBref match pages and player stat tables.

    Only `fetch_match_detail` and `fetch_player_stats` are implemented in
    Phase 1; full schedule scraping is deferred to Phase 2 (the schedule page
    contains a giant table whose stable selector changes between competitions).
    """

    DEFAULT_RATE_LIMIT: RateLimitConfig = RateLimitConfig(
        requests_per_second=1 / 3,  # 1 req / 3 s
        burst_size=1,
    )

    def __init__(
        self,
        *,
        base_url: str = FBREF_BASE_URL,
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
        # 403 → blocked by FBref; retry after proxy swap.
        self._retryable_status = self._retryable_status | {403}

    # --- Public API ---

    def get_rate_limit(self) -> RateLimitConfig:
        return self.DEFAULT_RATE_LIMIT

    async def health_check(self) -> bool:
        try:
            response = await self._request_with_retry("/en/", max_retries=1)
        except DataFetchError:
            return False
        return response.status_code == 200

    async def fetch_matches(self, season_id: str | int) -> list[MatchDTO]:
        # TODO(Phase 2): schedule-page parsing. Each league has a different
        # table id (`sched_2022-2023_9_1`, etc.), so a generic implementation
        # needs a per-league config. Lean on API-Football for fixtures until then.
        raise AdapterMethodNotSupported(
            "FBrefAdapter.fetch_matches is deferred to Phase 2"
        )

    async def fetch_match_detail(self, match_id: str | int) -> MatchDetailDTO:
        soup = await self._fetch_match_soup(str(match_id))
        match_dto = self._parse_match_header(soup, str(match_id))
        home_stats, away_stats = self._parse_team_stats(soup, str(match_id))
        return MatchDetailDTO(
            match=match_dto,
            home_stats=home_stats,
            away_stats=away_stats,
            player_stats=self._parse_player_stats(soup, str(match_id)),
        )

    async def fetch_team_stats(
        self, team_id: str | int, season_id: str | int
    ) -> TeamStatsDTO:
        # TODO(Phase 2): per-team season aggregate page (`/en/squads/{id}/`).
        raise AdapterMethodNotSupported(
            "FBrefAdapter.fetch_team_stats is deferred to Phase 2"
        )

    async def fetch_player_stats(self, match_id: str | int) -> list[PlayerStatDTO]:
        soup = await self._fetch_match_soup(str(match_id))
        return self._parse_player_stats(soup, str(match_id))

    # --- Hooks (UA rotation + 403 → proxy swap) ---

    def _get_extra_headers(self) -> dict[str, str]:
        return {"User-Agent": random_user_agent()}

    async def _on_blocked(self, response: httpx.Response) -> None:
        proxy = await self._proxy_pool.get()
        if proxy is None:
            self._log.error("fbref_blocked_no_proxy", url=str(response.request.url))
            return
        # Closing the existing client and re-creating with a proxy. The
        # surrounding retry loop will use the new client on next attempt.
        await self._client.aclose()
        self._client = httpx.AsyncClient(
            base_url=str(self._client.base_url),
            timeout=self._client.timeout,
            proxy=proxy,
        )
        self._log.warning("fbref_proxy_swapped", proxy=_redact_proxy(proxy))

    # --- Internal: HTTP / parsing ---

    async def _fetch_match_soup(self, match_id: str) -> BeautifulSoup:
        path = f"/en/matches/{match_id}"
        response = await self._request_with_retry(path)
        return BeautifulSoup(response.text, "lxml")

    def _parse_match_header(self, soup: BeautifulSoup, match_id: str) -> MatchDTO:
        # FBref puts kickoff data in a `<meta>` and the scorebox `<div>`.
        # TODO(Phase 2): full venue/round extraction. The Phase-1 ingest path
        # only feeds player stats; the matches table is populated upstream by
        # API-Football, so a stub MatchDTO is enough here.
        scorebox = soup.find("div", class_="scorebox")
        if not isinstance(scorebox, Tag):
            raise DataFetchError(SOURCE_NAME, f"scorebox not found on match {match_id}")

        team_links = scorebox.find_all("a", href=True)
        team_names = [link.get_text(strip=True) for link in team_links if "/squads/" in link["href"]]
        if len(team_names) < 2:
            raise DataFetchError(SOURCE_NAME, f"team names not found on match {match_id}")

        date_meta = soup.find("meta", attrs={"itemprop": "startDate"})
        match_dt = (
            datetime.fromisoformat(date_meta["content"]).astimezone(timezone.utc)
            if isinstance(date_meta, Tag) and date_meta.get("content")
            else datetime.now(timezone.utc)
        )

        return MatchDTO(
            external_id=match_id,
            home_team_name=team_names[0],
            away_team_name=team_names[1],
            match_date=match_dt,
            status="finished",
            home_score=None,
            away_score=None,
            venue=None,
            round=None,
            competition_name=_text_or(soup.find("a", href=lambda href: bool(href and "/comps/" in href)), "unknown"),
            season_year=match_dt.year,
        )

    def _parse_team_stats(
        self,
        soup: BeautifulSoup,
        match_id: str,
    ) -> tuple[MatchStatsDTO | None, MatchStatsDTO | None]:
        # FBref renders a "Team Stats" panel with possession, passing accuracy,
        # shots on target. xG is in a separate per-team summary table.
        team_stats_panel = soup.find("div", id="team_stats")
        if not isinstance(team_stats_panel, Tag):
            return None, None

        rows = team_stats_panel.find_all("tr")
        kv: dict[str, list[str]] = {}
        current_label: str | None = None
        for row in rows:
            th = row.find("th")
            if isinstance(th, Tag) and th.get("colspan"):
                current_label = th.get_text(strip=True)
                continue
            tds = row.find_all("td")
            if current_label and len(tds) >= 2:
                kv[current_label] = [td.get_text(" ", strip=True) for td in tds[:2]]

        home_stats = self._build_team_stats(kv, match_id, is_home=True)
        away_stats = self._build_team_stats(kv, match_id, is_home=False)
        return home_stats, away_stats

    def _build_team_stats(
        self, kv: dict[str, list[str]], match_id: str, *, is_home: bool
    ) -> MatchStatsDTO | None:
        idx = 0 if is_home else 1
        possession = _percent(kv.get("Possession", [None, None])[idx])
        pass_acc = _percent(kv.get("Passing Accuracy", [None, None])[idx])
        if possession is None and pass_acc is None:
            return None
        return MatchStatsDTO(
            match_external_id=match_id,
            team_external_id=f"{match_id}:{'home' if is_home else 'away'}",
            is_home=is_home,
            possession=possession,
            pass_accuracy=pass_acc,
            data_source=SOURCE_NAME,
            # TODO(Phase 2): xG / shots / fouls — extracted from the per-team
            # summary table (`stats_*_summary`), needs a more involved selector.
        )

    def _parse_player_stats(
        self,
        soup: BeautifulSoup,
        match_id: str,
    ) -> list[PlayerStatDTO]:
        out: list[PlayerStatDTO] = []
        # FBref player-stat tables have ids like `stats_{team_id}_summary`.
        for table in soup.find_all("table", id=lambda v: bool(v and v.endswith("_summary"))):
            if not isinstance(table, Tag):
                continue
            team_token = (table.get("id") or "").removeprefix("stats_").removesuffix("_summary")
            for row in table.find("tbody").find_all("tr"):
                if not isinstance(row, Tag) or row.get("class") and "thead" in row["class"]:
                    continue
                player_cell = row.find("th", attrs={"data-stat": "player"})
                if not isinstance(player_cell, Tag):
                    continue
                anchor = player_cell.find("a", href=True)
                if not isinstance(anchor, Tag):
                    continue
                player_id = _player_id_from_href(anchor["href"])
                if player_id is None:
                    continue
                out.append(
                    PlayerStatDTO(
                        match_external_id=match_id,
                        player_external_id=player_id,
                        team_external_id=team_token,
                        goals=_cell_int(row, "goals") or 0,
                        assists=_cell_int(row, "assists") or 0,
                        xg=_cell_decimal(row, "xg"),
                        xa=_cell_decimal(row, "xg_assist"),
                        shots=_cell_int(row, "shots"),
                        key_passes=_cell_int(row, "passes_into_final_third"),
                        tackles=_cell_int(row, "tackles"),
                        interceptions=_cell_int(row, "interceptions"),
                        saves=None,
                        yellow_cards=_cell_int(row, "cards_yellow") or 0,
                        red_cards=_cell_int(row, "cards_red") or 0,
                    )
                )
        return out


# --- Module-level parser helpers ---


def _text_or(node: Tag | None, default: str) -> str:
    if node is None or not isinstance(node, Tag):
        return default
    return node.get_text(strip=True) or default


def _percent(raw: str | None) -> Decimal | None:
    if not raw:
        return None
    text = raw.strip().rstrip("%")
    try:
        return Decimal(text)
    except (ValueError, ArithmeticError):
        return None


def _cell_int(row: Tag, stat_name: str) -> int | None:
    cell = row.find("td", attrs={"data-stat": stat_name})
    if not isinstance(cell, Tag):
        return None
    text = cell.get_text(strip=True)
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def _cell_decimal(row: Tag, stat_name: str) -> Decimal | None:
    cell = row.find("td", attrs={"data-stat": stat_name})
    if not isinstance(cell, Tag):
        return None
    text = cell.get_text(strip=True)
    if not text:
        return None
    try:
        return Decimal(text)
    except (ValueError, ArithmeticError):
        return None


def _player_id_from_href(href: str) -> str | None:
    # `/en/players/0d6f2e9d/Lionel-Messi` → "0d6f2e9d"
    parts = href.strip("/").split("/")
    if len(parts) >= 3 and parts[0] == "en" and parts[1] == "players":
        return parts[2]
    return None


def _redact_proxy(url: str) -> str:
    # Strip credentials before logging.
    if "@" in url:
        return url.split("@", 1)[-1]
    return url

"""API-Football REST adapter.

Wraps the v3 endpoints used by the ingest pipelines. Auth is via the
``x-apisports-key`` header (or RapidAPI variant). Free-tier accounts are
limited to ~100 req/day, so callers should rely on the rate limiter and on
caching (`_cache_ttl_seconds`) for any volume work.

Docs: https://www.api-football.com/documentation-v3
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

import structlog

from src.adapters.base import (
    BaseDataSourceAdapter,
    DataFetchError,
)
from src.config.settings import settings
from src.dto.match import MatchDTO
from src.dto.player import PlayerStatDTO
from src.dto.stats import MatchDetailDTO, MatchStatsDTO, TeamStatsDTO
from src.utils.rate_limiter import RateLimitConfig

logger = structlog.get_logger(__name__)

API_FOOTBALL_BASE_URL: str = "https://v3.football.api-sports.io"
SOURCE_NAME: str = "api_football"

# API-Football's `fixture.status.short` codes mapped to our internal status.
_STATUS_MAP: dict[str, str] = {
    "TBD": "scheduled", "NS": "scheduled",
    "1H": "live", "HT": "live", "2H": "live", "ET": "live",
    "BT": "live", "P": "live", "LIVE": "live", "INT": "live",
    "FT": "finished", "AET": "finished", "PEN": "finished",
    "PST": "postponed",
    "CANC": "cancelled", "ABD": "cancelled", "AWD": "cancelled",
    "WO": "cancelled", "SUSP": "cancelled",
}


def map_status(short_code: str) -> str:
    """Translate API-Football short status to our internal vocabulary."""
    return _STATUS_MAP.get(short_code, "scheduled")


class ApiFootballAdapter(BaseDataSourceAdapter):
    """REST adapter for API-Football v3.

    Default rate limit reflects the documented free tier (~100 req/day,
    plenty of headroom for one-shot pulls). Heavier workloads should pass an
    explicit ``rate_limit`` reflecting the user's actual subscription.
    """

    # The free tier is 10 req/min — undershoot to 8/min (one every 7.5s) and
    # disable bursting so a tight loop never trips the 429 ceiling. Paid tiers
    # should override via the constructor's `rate_limit` argument.
    DEFAULT_RATE_LIMIT: RateLimitConfig = RateLimitConfig(
        requests_per_second=8 / 60,
        burst_size=1,
    )

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str = API_FOOTBALL_BASE_URL,
        rate_limit: RateLimitConfig | None = None,
        **kwargs: Any,
    ) -> None:
        key = api_key if api_key is not None else settings.API_FOOTBALL_KEY
        if not key:
            raise ValueError("ApiFootballAdapter requires API_FOOTBALL_KEY")
        super().__init__(
            SOURCE_NAME,
            rate_limit=rate_limit or self.DEFAULT_RATE_LIMIT,
            base_url=base_url,
            default_headers={"x-apisports-key": key, "Accept": "application/json"},
            **kwargs,
        )

    # --- Public API ---

    def get_rate_limit(self) -> RateLimitConfig:
        return self.DEFAULT_RATE_LIMIT

    async def health_check(self) -> bool:
        try:
            response = await self._request_with_retry("/status", max_retries=1)
        except DataFetchError:
            return False
        return response.status_code == 200

    async def fetch_matches(self, season_id: str | int) -> list[MatchDTO]:
        """Fetch every fixture in a season.

        `season_id` for this adapter is interpreted as ``"{league_id}:{year}"``
        (API-Football addresses competitions by league + year). E.g.
        ``"39:2024"`` for the 2024–25 Premier League.
        """
        league_id, year = _parse_season_id(season_id)
        params: dict[str, str | int] = {"league": league_id, "season": year}
        records = await self._paginate("/fixtures", params=params)
        return [self._fixture_to_match_dto(rec) for rec in records]

    async def fetch_match_detail(self, match_id: str | int) -> MatchDetailDTO:
        """Fetch fixture + team-level stats + (optional) player stats."""
        fixture = await self._fetch_fixture(int(match_id))
        match_dto = self._fixture_to_match_dto(fixture)

        stats_resp = await self._request_with_retry(
            "/fixtures/statistics", params={"fixture": int(match_id)}
        )
        stats_payload = _unwrap_response(stats_resp.json())

        home_id = fixture["teams"]["home"]["id"]
        away_id = fixture["teams"]["away"]["id"]
        # The /fixtures/statistics response omits fixture_id from each team
        # block, so we thread the parent fixture id through here. Without it
        # `match_external_id` lands as the empty string and StatsPipeline drops
        # the row at resolve time.
        fixture_id = int(fixture["fixture"]["id"])
        home_stats = self._team_stats_block(
            stats_payload, team_id=home_id, is_home=True, fixture_id=fixture_id
        )
        away_stats = self._team_stats_block(
            stats_payload, team_id=away_id, is_home=False, fixture_id=fixture_id
        )

        return MatchDetailDTO(
            match=match_dto,
            home_stats=home_stats,
            away_stats=away_stats,
            player_stats=await self.fetch_player_stats(match_id),
        )

    async def fetch_team_stats(
        self, team_id: str | int, season_id: str | int
    ) -> TeamStatsDTO:
        league_id, year = _parse_season_id(season_id)
        response = await self._request_with_retry(
            "/teams/statistics",
            params={"team": int(team_id), "league": league_id, "season": year},
        )
        body = response.json()
        if body.get("errors"):
            raise DataFetchError(SOURCE_NAME, f"errors={body['errors']}")
        payload = body.get("response") or {}
        return self._team_season_stats_to_dto(payload, team_id=int(team_id), season_id=str(season_id))

    async def fetch_player_stats(self, match_id: str | int) -> list[PlayerStatDTO]:
        response = await self._request_with_retry(
            "/fixtures/players", params={"fixture": int(match_id)}
        )
        teams = _unwrap_response(response.json())
        out: list[PlayerStatDTO] = []
        for team_block in teams:
            team_id = team_block["team"]["id"]
            for player_entry in team_block.get("players", []):
                out.append(
                    self._player_block_to_dto(
                        player_entry, match_id=int(match_id), team_id=team_id
                    )
                )
        return out

    # --- Internal: HTTP / pagination ---

    async def _paginate(
        self,
        path: str,
        *,
        params: dict[str, str | int],
        max_pages: int = 50,
    ) -> list[dict[str, Any]]:
        """Walk API-Football's `paging.total` and concatenate `response` lists.

        Some endpoints (e.g. `/fixtures` filtered by league+season) reject the
        `page` query parameter outright when results fit on a single page, so
        we issue the first request without it and only paginate when the
        response advertises `paging.total > 1`.
        """
        out: list[dict[str, Any]] = []
        # First page: no `page` param.
        response = await self._request_with_retry(path, params=dict(params))
        body = response.json()
        if body.get("errors"):
            raise DataFetchError(SOURCE_NAME, f"errors={body['errors']}")
        out.extend(body.get("response") or [])
        paging = body.get("paging") or {}
        total = int(paging.get("total") or 1)
        page = 2
        while page <= total and page <= max_pages:
            response = await self._request_with_retry(path, params={**params, "page": page})
            body = response.json()
            if body.get("errors"):
                raise DataFetchError(SOURCE_NAME, f"errors={body['errors']}")
            out.extend(body.get("response") or [])
            page += 1
        return out

    async def _fetch_fixture(self, fixture_id: int) -> dict[str, Any]:
        response = await self._request_with_retry(
            "/fixtures", params={"id": fixture_id}
        )
        records = _unwrap_response(response.json())
        if not records:
            raise DataFetchError(SOURCE_NAME, f"fixture {fixture_id} not found")
        return records[0]

    # --- Internal: response → DTO mappers ---

    @staticmethod
    def _fixture_to_match_dto(rec: dict[str, Any]) -> MatchDTO:
        fixture = rec["fixture"]
        league = rec["league"]
        teams = rec["teams"]
        goals = rec.get("goals") or {}
        return MatchDTO(
            external_id=str(fixture["id"]),
            home_team_name=teams["home"]["name"],
            away_team_name=teams["away"]["name"],
            home_team_external_id=str(teams["home"]["id"]) if teams["home"].get("id") else None,
            away_team_external_id=str(teams["away"]["id"]) if teams["away"].get("id") else None,
            match_date=datetime.fromisoformat(fixture["date"].replace("Z", "+00:00")),
            status=map_status(fixture["status"]["short"]),
            home_score=goals.get("home"),
            away_score=goals.get("away"),
            venue=(fixture.get("venue") or {}).get("name"),
            round=league.get("round"),
            competition_name=league["name"],
            season_year=int(league["season"]),
        )

    def _team_stats_block(
        self,
        payload: list[dict[str, Any]],
        *,
        team_id: int,
        is_home: bool,
        fixture_id: int,
    ) -> MatchStatsDTO | None:
        block = next((b for b in payload if b["team"]["id"] == team_id), None)
        if block is None:
            return None
        stats = {item["type"]: item["value"] for item in block.get("statistics", [])}
        return MatchStatsDTO(
            match_external_id=str(fixture_id),
            team_external_id=str(team_id),
            is_home=is_home,
            possession=_pct(stats.get("Ball Possession")),
            shots=_int(stats.get("Total Shots")),
            shots_on_target=_int(stats.get("Shots on Goal")),
            xg=_decimal(stats.get("expected_goals")),
            xg_against=None,
            passes=_int(stats.get("Total passes")),
            pass_accuracy=_pct(stats.get("Passes %")),
            corners=_int(stats.get("Corner Kicks")),
            fouls=_int(stats.get("Fouls")),
            yellow_cards=_int(stats.get("Yellow Cards")),
            red_cards=_int(stats.get("Red Cards")),
            offsides=_int(stats.get("Offsides")),
            tackles=None,
            interceptions=None,
            saves=_int(stats.get("Goalkeeper Saves")),
            data_source=SOURCE_NAME,
        )

    @staticmethod
    def _team_season_stats_to_dto(
        payload: dict[str, Any], *, team_id: int, season_id: str
    ) -> TeamStatsDTO:
        fixtures = payload.get("fixtures") or {}
        played = (fixtures.get("played") or {}).get("total", 0)
        wins = (fixtures.get("wins") or {}).get("total", 0)
        draws = (fixtures.get("draws") or {}).get("total", 0)
        losses = (fixtures.get("loses") or {}).get("total", 0)
        goals = payload.get("goals") or {}
        gf = ((goals.get("for") or {}).get("total") or {}).get("total", 0)
        ga = ((goals.get("against") or {}).get("total") or {}).get("total", 0)
        clean_sheets = (payload.get("clean_sheet") or {}).get("total")
        return TeamStatsDTO(
            team_external_id=str(team_id),
            season_external_id=season_id,
            matches_played=int(played or 0),
            wins=int(wins or 0),
            draws=int(draws or 0),
            losses=int(losses or 0),
            goals_for=int(gf or 0),
            goals_against=int(ga or 0),
            xg_for=None,
            xg_against=None,
            clean_sheets=int(clean_sheets) if clean_sheets is not None else None,
            data_source=SOURCE_NAME,
        )

    @staticmethod
    def _player_block_to_dto(
        entry: dict[str, Any], *, match_id: int, team_id: int
    ) -> PlayerStatDTO:
        player = entry["player"]
        # API-Football wraps each player's match line in a single-element list.
        line = (entry.get("statistics") or [{}])[0]
        goals = line.get("goals") or {}
        cards = line.get("cards") or {}
        passes = line.get("passes") or {}
        tackles = line.get("tackles") or {}
        shots = line.get("shots") or {}
        return PlayerStatDTO(
            match_external_id=str(match_id),
            player_external_id=str(player["id"]),
            team_external_id=str(team_id),
            goals=_int(goals.get("total")) or 0,
            assists=_int(goals.get("assists")) or 0,
            xg=None,
            xa=None,
            shots=_int(shots.get("total")),
            key_passes=_int(passes.get("key")),
            tackles=_int(tackles.get("total")),
            interceptions=_int(tackles.get("interceptions")),
            saves=_int(goals.get("saves")),
            yellow_cards=_int(cards.get("yellow")) or 0,
            red_cards=_int(cards.get("red")) or 0,
        )


# --- Module-level helpers ---


def _parse_season_id(season_id: str | int) -> tuple[int, int]:
    """Split ``"{league}:{year}"`` into a ``(league_id, year)`` tuple."""
    if isinstance(season_id, int):
        raise ValueError(
            "ApiFootballAdapter season_id must be a 'league:year' string"
        )
    parts = season_id.split(":")
    if len(parts) != 2:
        raise ValueError(f"Invalid season_id {season_id!r}; expected 'league:year'")
    return int(parts[0]), int(parts[1])


def _unwrap_response(body: dict[str, Any]) -> list[dict[str, Any]]:
    """Pull the `response` array from an API-Football envelope, defaulting to []."""
    if body.get("errors"):
        raise DataFetchError(SOURCE_NAME, f"errors={body['errors']}")
    return list(body.get("response") or [])


def _int(value: Any) -> int | None:
    if value in (None, "", "null"):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _pct(value: Any) -> Decimal | None:
    """Parse a possession-style ``"55%"`` string to a Decimal between 0 and 100."""
    if value is None:
        return None
    text = str(value).strip().rstrip("%")
    try:
        return Decimal(text)
    except (ValueError, ArithmeticError):
        return None


def _decimal(value: Any) -> Decimal | None:
    if value in (None, "", "null"):
        return None
    try:
        return Decimal(str(value))
    except (ValueError, ArithmeticError):
        return None

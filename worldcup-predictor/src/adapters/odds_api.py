"""the-odds-api.com REST adapter (live bookmaker odds).

Free tier is capped at 500 requests/month, so paths are kept tight: we never
poll an event individually if it can be batched per sport. Long-tail requests
should be scheduled around match kickoff time to maximize signal per call.

`season_id` for this adapter is the sport key (e.g. ``"soccer_fifa_world_cup"``,
``"soccer_epl"``). `match_id` is the OddsAPI event UUID — *not* the
API-Football fixture id — so the pipeline must translate via the matches table.

Docs: https://the-odds-api.com/liveapi/guides/v4/
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

import structlog

from src.adapters.base import (
    AdapterMethodNotSupported,
    BaseDataSourceAdapter,
    DataFetchError,
)
from src.config.settings import settings
from src.dto.match import MatchDTO
from src.dto.odds import OddsDTO
from src.dto.player import PlayerStatDTO
from src.dto.stats import MatchDetailDTO, TeamStatsDTO
from src.utils.rate_limiter import RateLimitConfig

logger = structlog.get_logger(__name__)

ODDS_API_BASE_URL: str = "https://api.the-odds-api.com"
SOURCE_NAME: str = "odds_api"

# Mapping from OddsAPI's `markets` keys to our `market_type` vocabulary.
_MARKET_MAP: dict[str, str] = {
    "h2h": "1x2",
    "totals": "over_under",
    "spreads": "asian_handicap",
}


class OddsApiAdapter(BaseDataSourceAdapter):
    """REST adapter for the-odds-api.com.

    Methods that don't apply to an odds-only source (`fetch_team_stats`,
    `fetch_player_stats`) raise `AdapterMethodNotSupported` rather than
    silently returning empty payloads.
    """

    DEFAULT_RATE_LIMIT: RateLimitConfig = RateLimitConfig(
        requests_per_second=1.0,
        burst_size=3,
    )
    DEFAULT_REGIONS: str = "eu"
    DEFAULT_MARKETS: str = "h2h,totals"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str = ODDS_API_BASE_URL,
        rate_limit: RateLimitConfig | None = None,
        regions: str = DEFAULT_REGIONS,
        markets: str = DEFAULT_MARKETS,
        **kwargs: Any,
    ) -> None:
        key = api_key if api_key is not None else settings.ODDS_API_KEY
        if not key:
            raise ValueError("OddsApiAdapter requires ODDS_API_KEY")
        super().__init__(
            SOURCE_NAME,
            rate_limit=rate_limit or self.DEFAULT_RATE_LIMIT,
            base_url=base_url,
            default_headers={"Accept": "application/json"},
            **kwargs,
        )
        self._api_key = key
        self._regions = regions
        self._markets = markets

    # --- Public API ---

    def get_rate_limit(self) -> RateLimitConfig:
        return self.DEFAULT_RATE_LIMIT

    async def health_check(self) -> bool:
        try:
            response = await self._request_with_retry(
                "/v4/sports", params={"apiKey": self._api_key}, max_retries=1
            )
        except DataFetchError:
            return False
        return response.status_code == 200

    async def fetch_matches(self, season_id: str | int) -> list[MatchDTO]:
        events = await self._fetch_sport_events(str(season_id))
        return [self._event_to_match_dto(event, sport_key=str(season_id)) for event in events]

    async def fetch_match_detail(self, match_id: str | int) -> MatchDetailDTO:
        """Resolve an event id into a `MatchDetailDTO` whose `odds` list is populated.

        Stats / player_stats stay empty because OddsAPI doesn't carry them.
        """
        event = await self._fetch_event_by_id(str(match_id))
        match_dto = self._event_to_match_dto(event, sport_key=event.get("sport_key", ""))
        odds = self._event_to_odds_dtos(event)
        return MatchDetailDTO(match=match_dto, odds=odds)

    async def fetch_team_stats(
        self, team_id: str | int, season_id: str | int
    ) -> TeamStatsDTO:
        raise AdapterMethodNotSupported(
            "OddsApiAdapter does not provide team season stats"
        )

    async def fetch_player_stats(self, match_id: str | int) -> list[PlayerStatDTO]:
        raise AdapterMethodNotSupported(
            "OddsApiAdapter does not provide player stats"
        )

    # --- Internal: HTTP ---

    async def _fetch_sport_events(self, sport_key: str) -> list[dict[str, Any]]:
        response = await self._request_with_retry(
            f"/v4/sports/{sport_key}/odds",
            params={
                "apiKey": self._api_key,
                "regions": self._regions,
                "markets": self._markets,
                "oddsFormat": "decimal",
                "dateFormat": "iso",
            },
        )
        body = response.json()
        if isinstance(body, dict) and body.get("error_code"):
            raise DataFetchError(SOURCE_NAME, str(body))
        return list(body or [])

    async def _fetch_event_by_id(self, event_id: str) -> dict[str, Any]:
        # OddsAPI does have a per-event endpoint, but it requires the sport key
        # too. The pipeline passes a composite ``"{sport_key}:{event_id}"`` so
        # we can look it up directly.
        if ":" not in event_id:
            raise ValueError(
                "OddsApiAdapter match_id must be 'sport_key:event_id'"
            )
        sport_key, raw_event = event_id.split(":", 1)
        response = await self._request_with_retry(
            f"/v4/sports/{sport_key}/events/{raw_event}/odds",
            params={
                "apiKey": self._api_key,
                "regions": self._regions,
                "markets": self._markets,
                "oddsFormat": "decimal",
                "dateFormat": "iso",
            },
        )
        body = response.json()
        if not body:
            raise DataFetchError(SOURCE_NAME, f"event {event_id} not found")
        return body

    # --- Internal: response → DTO mappers ---

    @staticmethod
    def _event_to_match_dto(event: dict[str, Any], *, sport_key: str) -> MatchDTO:
        commence = datetime.fromisoformat(
            event["commence_time"].replace("Z", "+00:00")
        )
        return MatchDTO(
            external_id=str(event["id"]),
            home_team_name=event["home_team"],
            away_team_name=event["away_team"],
            match_date=commence,
            status="scheduled",  # OddsAPI doesn't carry kickoff status
            home_score=None,
            away_score=None,
            venue=None,
            round=None,
            competition_name=event.get("sport_title") or sport_key,
            season_year=commence.year,
        )

    def _event_to_odds_dtos(self, event: dict[str, Any]) -> list[OddsDTO]:
        out: list[OddsDTO] = []
        home_name = event.get("home_team")
        away_name = event.get("away_team")
        for book in event.get("bookmakers") or []:
            book_key = book.get("key", "")
            updated_at = self._parse_dt(book.get("last_update"))
            for market in book.get("markets") or []:
                market_type = _MARKET_MAP.get(market.get("key"))
                if market_type is None:
                    continue
                for dto in self._market_to_dto_chunks(
                    market=market,
                    bookmaker=book_key,
                    market_type=market_type,
                    snapshot_at=updated_at,
                    home_name=home_name,
                    away_name=away_name,
                    event_id=str(event["id"]),
                ):
                    out.append(dto)
        return out

    def _market_to_dto_chunks(
        self,
        *,
        market: dict[str, Any],
        bookmaker: str,
        market_type: str,
        snapshot_at: datetime,
        home_name: str | None,
        away_name: str | None,
        event_id: str,
    ) -> list[OddsDTO]:
        # OU/AH expose multiple lines under one market block; group by `point`.
        outcomes_by_line: dict[str | None, dict[str, float]] = {}
        for outcome in market.get("outcomes") or []:
            point = outcome.get("point")
            line_key = str(point) if point is not None else None
            label = self._label(outcome.get("name"), home_name, away_name, market_type)
            if label is None:
                continue
            outcomes_by_line.setdefault(line_key, {})[label] = float(outcome["price"])

        return [
            OddsDTO(
                match_external_id=event_id,
                bookmaker=bookmaker,
                market_type=market_type,
                market_value=line_key,
                outcomes=outcomes,
                snapshot_at=snapshot_at,
            )
            for line_key, outcomes in outcomes_by_line.items()
            if outcomes
        ]

    @staticmethod
    def _label(
        name: str | None,
        home_name: str | None,
        away_name: str | None,
        market_type: str,
    ) -> str | None:
        if name is None:
            return None
        if market_type == "1x2":
            if name == home_name:
                return "home"
            if name == away_name:
                return "away"
            if name.lower() == "draw":
                return "draw"
            return None
        if market_type == "over_under":
            return name.lower() if name.lower() in {"over", "under"} else None
        if market_type == "asian_handicap":
            if name == home_name:
                return "home"
            if name == away_name:
                return "away"
        return None

    @staticmethod
    def _parse_dt(value: str | None) -> datetime:
        if not value:
            raise ValueError("OddsAPI bookmaker.last_update missing")
        return datetime.fromisoformat(value.replace("Z", "+00:00"))

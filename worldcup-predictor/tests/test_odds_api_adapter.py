"""Unit tests for `OddsApiAdapter`."""
from __future__ import annotations

from typing import Any

import httpx
import pytest

from src.adapters.base import AdapterMethodNotSupported
from src.adapters.odds_api import OddsApiAdapter


def _event_payload() -> dict[str, Any]:
    return {
        "id": "evt-001",
        "sport_key": "soccer_fifa_world_cup",
        "sport_title": "FIFA World Cup",
        "commence_time": "2026-06-15T18:00:00Z",
        "home_team": "USA",
        "away_team": "Mexico",
        "bookmakers": [
            {
                "key": "pinnacle",
                "title": "Pinnacle",
                "last_update": "2026-06-14T12:00:00Z",
                "markets": [
                    {
                        "key": "h2h",
                        "outcomes": [
                            {"name": "USA", "price": 2.10},
                            {"name": "Draw", "price": 3.40},
                            {"name": "Mexico", "price": 3.30},
                        ],
                    },
                    {
                        "key": "totals",
                        "outcomes": [
                            {"name": "Over", "price": 1.95, "point": 2.5},
                            {"name": "Under", "price": 1.85, "point": 2.5},
                        ],
                    },
                ],
            }
        ],
    }


def _build_adapter(handler: httpx.MockTransport) -> OddsApiAdapter:
    return OddsApiAdapter(api_key="test", transport=handler)


@pytest.mark.asyncio
async def test_fetch_matches_maps_events_to_match_dtos() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "/v4/sports/soccer_fifa_world_cup/odds" in request.url.path
        return httpx.Response(200, json=[_event_payload()])

    adapter = _build_adapter(httpx.MockTransport(handler))
    try:
        matches = await adapter.fetch_matches("soccer_fifa_world_cup")
    finally:
        await adapter.aclose()

    assert len(matches) == 1
    match = matches[0]
    assert match.external_id == "evt-001"
    assert match.competition_name == "FIFA World Cup"
    assert match.status == "scheduled"


@pytest.mark.asyncio
async def test_fetch_match_detail_returns_h2h_and_totals_odds() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_event_payload())

    adapter = _build_adapter(httpx.MockTransport(handler))
    try:
        detail = await adapter.fetch_match_detail("soccer_fifa_world_cup:evt-001")
    finally:
        await adapter.aclose()

    market_types = sorted({odds.market_type for odds in detail.odds})
    assert market_types == ["1x2", "over_under"]

    h2h = next(o for o in detail.odds if o.market_type == "1x2")
    assert h2h.outcomes == {"home": 2.10, "draw": 3.40, "away": 3.30}

    ou = next(o for o in detail.odds if o.market_type == "over_under")
    assert ou.market_value == "2.5"
    assert ou.outcomes == {"over": 1.95, "under": 1.85}


@pytest.mark.asyncio
async def test_fetch_team_stats_raises_method_not_supported() -> None:
    adapter = OddsApiAdapter(api_key="test")
    try:
        with pytest.raises(AdapterMethodNotSupported):
            await adapter.fetch_team_stats(1, "soccer_fifa_world_cup")
    finally:
        await adapter.aclose()


@pytest.mark.asyncio
async def test_fetch_player_stats_raises_method_not_supported() -> None:
    adapter = OddsApiAdapter(api_key="test")
    try:
        with pytest.raises(AdapterMethodNotSupported):
            await adapter.fetch_player_stats(123)
    finally:
        await adapter.aclose()


def test_init_requires_api_key() -> None:
    with pytest.raises(ValueError):
        OddsApiAdapter(api_key="")

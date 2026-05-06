"""Unit tests for `ApiFootballAdapter`.

Uses `httpx.MockTransport` to fake the API-Football REST surface so tests run
offline and deterministically.
"""
from __future__ import annotations

from typing import Any

import httpx
import pytest

from src.adapters.api_football import (
    ApiFootballAdapter,
    _parse_season_id,
    map_status,
)


def _envelope(response: list[dict[str, Any]] | dict[str, Any]) -> dict[str, Any]:
    return {
        "get": "fixtures",
        "parameters": {},
        "errors": [],
        "results": len(response) if isinstance(response, list) else 1,
        "paging": {"current": 1, "total": 1},
        "response": response,
    }


def _fixture_payload() -> dict[str, Any]:
    return {
        "fixture": {
            "id": 12345,
            "date": "2026-06-15T18:00:00+00:00",
            "status": {"short": "FT"},
            "venue": {"name": "MetLife Stadium"},
        },
        "league": {"id": 1, "name": "FIFA World Cup", "season": 2026, "round": "Group A"},
        "teams": {"home": {"id": 11, "name": "USA"}, "away": {"id": 22, "name": "Mexico"}},
        "goals": {"home": 2, "away": 1},
    }


def _build_adapter(handler: httpx.MockTransport) -> ApiFootballAdapter:
    return ApiFootballAdapter(api_key="test-key", transport=handler)


def test_map_status_known_codes_translate_to_internal_vocabulary() -> None:
    assert map_status("NS") == "scheduled"
    assert map_status("1H") == "live"
    assert map_status("FT") == "finished"
    assert map_status("PST") == "postponed"
    assert map_status("CANC") == "cancelled"


def test_map_status_unknown_code_falls_back_to_scheduled() -> None:
    assert map_status("XYZ") == "scheduled"


def test_parse_season_id_valid_returns_league_and_year_tuple() -> None:
    assert _parse_season_id("39:2024") == (39, 2024)


def test_parse_season_id_missing_colon_raises() -> None:
    with pytest.raises(ValueError):
        _parse_season_id("just-a-string")


def test_parse_season_id_int_raises() -> None:
    with pytest.raises(ValueError):
        _parse_season_id(2024)


def test_init_requires_api_key() -> None:
    with pytest.raises(ValueError):
        ApiFootballAdapter(api_key="")


@pytest.mark.asyncio
async def test_fetch_matches_unwraps_envelope_and_maps_to_match_dto() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/fixtures"
        assert request.headers["x-apisports-key"] == "test-key"
        return httpx.Response(200, json=_envelope([_fixture_payload()]))

    adapter = _build_adapter(httpx.MockTransport(handler))
    try:
        matches = await adapter.fetch_matches("1:2026")
    finally:
        await adapter.aclose()

    assert len(matches) == 1
    match = matches[0]
    assert match.external_id == "12345"
    assert match.home_team_name == "USA"
    assert match.away_team_name == "Mexico"
    assert match.status == "finished"
    assert match.home_score == 2 and match.away_score == 1
    assert match.competition_name == "FIFA World Cup"
    assert match.season_year == 2026
    assert match.venue == "MetLife Stadium"
    assert match.round == "Group A"
    # Team external ids are threaded through so MatchPipeline can stamp
    # `teams.api_football_id` onto the resolved teams row — without this
    # StatsPipeline cannot resolve teams when later pulling /fixtures/statistics.
    assert match.home_team_external_id == "11"
    assert match.away_team_external_id == "22"


@pytest.mark.asyncio
async def test_fetch_match_detail_threads_fixture_id_into_stats_dtos() -> None:
    """Regression: /fixtures/statistics blocks omit fixture_id, so
    `_team_stats_block` must receive it from the parent fixture call.
    Without this fix, MatchStatsDTO.match_external_id was '' and
    StatsPipeline._resolve_match dropped every row at int-parse."""
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/fixtures":
            return httpx.Response(200, json=_envelope([_fixture_payload()]))
        if request.url.path == "/fixtures/statistics":
            return httpx.Response(200, json=_envelope([
                {"team": {"id": 11, "name": "USA"}, "statistics": [
                    {"type": "Ball Possession", "value": "55%"},
                    {"type": "expected_goals", "value": "1.42"},
                ]},
                {"team": {"id": 22, "name": "Mexico"}, "statistics": [
                    {"type": "Ball Possession", "value": "45%"},
                    {"type": "expected_goals", "value": "0.88"},
                ]},
            ]))
        if request.url.path == "/fixtures/players":
            return httpx.Response(200, json=_envelope([]))
        raise AssertionError(f"unexpected path {request.url.path}")

    adapter = _build_adapter(httpx.MockTransport(handler))
    try:
        detail = await adapter.fetch_match_detail(12345)
    finally:
        await adapter.aclose()

    assert detail.home_stats is not None and detail.away_stats is not None
    assert detail.home_stats.match_external_id == "12345"
    assert detail.away_stats.match_external_id == "12345"
    assert float(detail.home_stats.xg) == pytest.approx(1.42)
    assert float(detail.away_stats.xg) == pytest.approx(0.88)


@pytest.mark.asyncio
async def test_fetch_matches_returns_empty_when_response_is_empty() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_envelope([]))

    adapter = _build_adapter(httpx.MockTransport(handler))
    try:
        matches = await adapter.fetch_matches("1:2026")
    finally:
        await adapter.aclose()

    assert matches == []

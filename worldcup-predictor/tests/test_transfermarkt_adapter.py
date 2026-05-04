"""Unit tests for `TransfermarktAdapter`.

Covers the JSON valuations endpoint and the HTML profile parser. Injuries
and full profile parsing are stubbed in the adapter (Phase 2 work) so they're
not asserted here.
"""
from __future__ import annotations

import httpx
import pytest

from src.adapters.base import AdapterMethodNotSupported
from src.adapters.transfermarkt import (
    TransfermarktAdapter,
    _parse_tm_date,
    _player_id_from_href,
    _safe_parse_tm_date,
)


def test_player_id_from_href_extracts_numeric_id() -> None:
    assert _player_id_from_href("/lionel-messi/profil/spieler/28003") == "28003"
    assert _player_id_from_href("/foo/bar") is None


def test_parse_tm_date_handles_us_locale() -> None:
    assert _parse_tm_date("Aug 1, 2024").isoformat() == "2024-08-01"


def test_safe_parse_tm_date_returns_none_on_unknowns() -> None:
    assert _safe_parse_tm_date("?") is None
    assert _safe_parse_tm_date("") is None
    assert _safe_parse_tm_date("not-a-date") is None


@pytest.mark.asyncio
async def test_fetch_valuations_maps_graph_endpoint_to_dtos() -> None:
    payload = {
        "list": [
            {"datum_mw": 1_700_000_000_000, "mw": 50_000_000, "verein": 11},
            {"datum_mw": 1_705_000_000_000, "mw": 55_000_000, "verein": 11},
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/ceapi/marketValueDevelopment/graph/28003"
        return httpx.Response(200, json=payload)

    adapter = TransfermarktAdapter(transport=httpx.MockTransport(handler))
    try:
        valuations = await adapter.fetch_valuations(28003)
    finally:
        await adapter.aclose()

    assert len(valuations) == 2
    assert valuations[0].player_external_id == "28003"
    assert valuations[0].market_value_eur == 50_000_000
    assert valuations[0].team_external_id == "11"


@pytest.mark.asyncio
async def test_fetch_player_profile_extracts_name() -> None:
    html = """
    <html><body>
      <h1 class="data-header__headline-wrapper">
        <span>#10</span> Lionel Messi
      </h1>
    </body></html>
    """

    def handler(request: httpx.Request) -> httpx.Response:
        assert "/profil/spieler/28003" in request.url.path
        return httpx.Response(200, text=html)

    adapter = TransfermarktAdapter(transport=httpx.MockTransport(handler))
    try:
        player = await adapter.fetch_player_profile(28003)
    finally:
        await adapter.aclose()

    assert player.external_id == "28003"
    assert player.name == "Lionel Messi"


@pytest.mark.asyncio
async def test_fetch_match_detail_raises_method_not_supported() -> None:
    adapter = TransfermarktAdapter()
    try:
        with pytest.raises(AdapterMethodNotSupported):
            await adapter.fetch_match_detail(1)
    finally:
        await adapter.aclose()


@pytest.mark.asyncio
async def test_init_extends_retryable_status_with_403() -> None:
    adapter = TransfermarktAdapter()
    try:
        assert 403 in adapter._retryable_status
    finally:
        await adapter.aclose()

"""Unit tests for `FBrefAdapter`.

Focus: parsing helpers + UA rotation + 403→retryable wiring. The full HTML
parser is exercised against a fixture page that mirrors the structure of
fbref.com match summaries (anchors under `.scorebox`, `<table id="stats_*_summary">`).
"""
from __future__ import annotations

import httpx
import pytest

from src.adapters.base import AdapterMethodNotSupported
from src.adapters.fbref import (
    FBrefAdapter,
    _percent,
    _player_id_from_href,
    _redact_proxy,
)

_MATCH_HTML = """
<html><head>
  <meta itemprop="startDate" content="2026-06-15T18:00:00+00:00">
</head><body>
  <a href="/en/comps/1/Premier-League">Premier League</a>
  <div class="scorebox">
    <a href="/en/squads/abc/USA">USA</a>
    <a href="/en/squads/def/Mexico">Mexico</a>
  </div>
  <table id="stats_abc_summary">
    <tbody>
      <tr>
        <th data-stat="player"><a href="/en/players/0d6f2e9d/Lionel-Messi">Lionel Messi</a></th>
        <td data-stat="goals">1</td>
        <td data-stat="assists">2</td>
        <td data-stat="xg">0.85</td>
        <td data-stat="xg_assist">0.50</td>
        <td data-stat="shots">3</td>
        <td data-stat="cards_yellow">0</td>
        <td data-stat="cards_red">0</td>
      </tr>
    </tbody>
  </table>
</body></html>
"""


def test_percent_strips_trailing_sign() -> None:
    assert _percent("55%") == _percent("55") and _percent("55%") is not None
    assert _percent(None) is None
    assert _percent("not-a-number") is None


def test_player_id_from_href_extracts_8char_hex() -> None:
    assert _player_id_from_href("/en/players/0d6f2e9d/Lionel-Messi") == "0d6f2e9d"
    assert _player_id_from_href("/en/squads/abc/Argentina") is None


def test_redact_proxy_strips_credentials() -> None:
    assert _redact_proxy("http://user:secret@1.2.3.4:8080") == "1.2.3.4:8080"
    assert _redact_proxy("http://1.2.3.4:8080") == "http://1.2.3.4:8080"


def test_init_extends_retryable_status_with_403() -> None:
    adapter = FBrefAdapter()
    try:
        assert 403 in adapter._retryable_status
        assert 429 in adapter._retryable_status  # default still present
    finally:
        # Sync close — pytest doesn't have an event loop yet here.
        import asyncio

        asyncio.run(adapter.aclose())


@pytest.mark.asyncio
async def test_fetch_match_detail_parses_player_grid() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.startswith("/en/matches/")
        return httpx.Response(200, text=_MATCH_HTML)

    adapter = FBrefAdapter(transport=httpx.MockTransport(handler))
    try:
        detail = await adapter.fetch_match_detail("cc5b4244")
    finally:
        await adapter.aclose()

    assert detail.match.home_team_name == "USA"
    assert detail.match.away_team_name == "Mexico"
    assert detail.match.competition_name == "Premier League"

    assert len(detail.player_stats) == 1
    stat = detail.player_stats[0]
    assert stat.player_external_id == "0d6f2e9d"
    assert stat.team_external_id == "abc"
    assert stat.goals == 1 and stat.assists == 2
    assert stat.shots == 3


@pytest.mark.asyncio
async def test_fetch_matches_raises_method_not_supported() -> None:
    adapter = FBrefAdapter()
    try:
        with pytest.raises(AdapterMethodNotSupported):
            await adapter.fetch_matches("anything")
    finally:
        await adapter.aclose()

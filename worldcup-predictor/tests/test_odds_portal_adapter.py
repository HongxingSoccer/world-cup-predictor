"""Unit tests for `OddsPortalAdapter` (Phase 1 skeleton).

Phase 1 adapter only needs to: construct cleanly, expose its rate limit,
mark methods as deferred / unsupported, and respond to a homepage health
check via the HTTP layer (not Playwright). Browser-driven flows are tested
in Phase 2 integration suites.
"""
from __future__ import annotations

import httpx
import pytest

from src.adapters.base import AdapterMethodNotSupported
from src.adapters.odds_portal import OddsPortalAdapter


@pytest.mark.asyncio
async def test_get_rate_limit_returns_default() -> None:
    adapter = OddsPortalAdapter()
    try:
        config = adapter.get_rate_limit()
        assert config.requests_per_second == pytest.approx(1 / 5)
        assert config.burst_size == 1
    finally:
        await adapter.aclose()


@pytest.mark.asyncio
async def test_init_extends_retryable_status_with_403() -> None:
    adapter = OddsPortalAdapter()
    try:
        assert 403 in adapter._retryable_status
    finally:
        await adapter.aclose()


@pytest.mark.asyncio
async def test_health_check_returns_true_for_200_homepage() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html></html>")

    adapter = OddsPortalAdapter(transport=httpx.MockTransport(handler))
    try:
        assert await adapter.health_check() is True
    finally:
        await adapter.aclose()


@pytest.mark.asyncio
async def test_phase1_methods_raise_method_not_supported() -> None:
    adapter = OddsPortalAdapter()
    try:
        with pytest.raises(AdapterMethodNotSupported):
            await adapter.fetch_matches("anything")
        with pytest.raises(AdapterMethodNotSupported):
            await adapter.fetch_match_detail("anything")
        with pytest.raises(AdapterMethodNotSupported):
            await adapter.fetch_team_stats(1, "anything")
        with pytest.raises(AdapterMethodNotSupported):
            await adapter.fetch_player_stats(1)
    finally:
        await adapter.aclose()


@pytest.mark.asyncio
async def test_fetch_historical_odds_phase1_returns_empty() -> None:
    """Stub exists, returns []. Real implementation lands in Phase 2."""
    # We don't call the real Playwright path: ensure_browser() would import
    # playwright. Patch it out.
    adapter = OddsPortalAdapter()
    try:
        async def _noop_browser() -> None:
            return None

        adapter.ensure_browser = _noop_browser  # type: ignore[method-assign]
        result = await adapter.fetch_historical_odds("https://example.invalid/match")
    finally:
        await adapter.aclose()

    assert result == []

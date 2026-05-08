"""GET /api/v1/fx/usd-cny — live USD→CNY exchange rate.

Hits ``frankfurter.app`` (free, no key, ECB rates) and caches the result in
process for ``CACHE_TTL_SECONDS``. Falls back to a conservative hardcoded
rate when the upstream is unreachable so the subscribe page never shows
``—`` for the CNY amount.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Optional

import httpx
import structlog
from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/v1/fx", tags=["fx"])

UPSTREAM_URL = "https://api.frankfurter.app/latest?from=USD&to=CNY"
CACHE_TTL_SECONDS: int = 60 * 60  # 1 hour
FALLBACK_RATE: float = 7.20
FALLBACK_SOURCE: str = "fallback"

_cache: dict[str, object] = {"rate": None, "source": None, "as_of": None, "fetched_at": 0.0}


class FxRateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pair: str  # always "USD/CNY" for now
    rate: float
    source: str  # provider name or "fallback"
    as_of: datetime
    cached: bool = False


@router.get("/usd-cny", response_model=FxRateResponse)
def usd_cny_rate() -> FxRateResponse:
    """Return the latest cached USD→CNY rate, refreshing if older than TTL."""
    now = time.monotonic()
    cached_rate = _cache.get("rate")
    if (
        cached_rate is not None
        and now - float(_cache["fetched_at"]) < CACHE_TTL_SECONDS
    ):
        return FxRateResponse(
            pair="USD/CNY",
            rate=float(cached_rate),
            source=str(_cache["source"]),
            as_of=_coerce_dt(_cache["as_of"]),
            cached=True,
        )

    fresh = _fetch_upstream()
    if fresh is not None:
        rate, as_of = fresh
        _cache.update(
            {
                "rate": rate,
                "source": "frankfurter.app",
                "as_of": as_of,
                "fetched_at": now,
            }
        )
        return FxRateResponse(
            pair="USD/CNY", rate=rate, source="frankfurter.app", as_of=as_of, cached=False
        )

    # Upstream failed and we have no cached value — emit the fallback
    # constant. Keep fetched_at unchanged so the next request retries.
    if cached_rate is not None:
        return FxRateResponse(
            pair="USD/CNY",
            rate=float(cached_rate),
            source=str(_cache["source"]),
            as_of=_coerce_dt(_cache["as_of"]),
            cached=True,
        )
    return FxRateResponse(
        pair="USD/CNY",
        rate=FALLBACK_RATE,
        source=FALLBACK_SOURCE,
        as_of=datetime.now(timezone.utc),
        cached=False,
    )


def _fetch_upstream() -> Optional[tuple[float, datetime]]:
    try:
        with httpx.Client(timeout=4.0) as client:
            response = client.get(UPSTREAM_URL)
            response.raise_for_status()
            payload = response.json()
        rate = float(payload["rates"]["CNY"])
        as_of_str = payload.get("date")
        as_of = (
            datetime.fromisoformat(as_of_str).replace(tzinfo=timezone.utc)
            if as_of_str
            else datetime.now(timezone.utc)
        )
        return rate, as_of
    except Exception as exc:  # noqa: BLE001 — defensive against any transport err
        logger.warning("fx_fetch_failed", error=str(exc))
        return None


def _coerce_dt(value: object) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.now(timezone.utc)

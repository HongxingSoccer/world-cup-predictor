"""Abstract base class for all external data-source adapters.

Subclasses implement provider-specific fetch logic (API-Football, Odds-API,
FBref, Transfermarkt). The base class provides shared concerns: rate limiting,
retry-with-backoff, response validation, audit logging to `data_source_logs`,
plus extension hooks for User-Agent rotation and proxy switching used by the
HTML-scraping adapters.

Threading / concurrency: each adapter instance owns one `httpx.AsyncClient`
and one `RateLimiter`. Construct one adapter per task / worker, not one per
request — both objects amortize state across calls.
"""
from __future__ import annotations

import asyncio
import random
from abc import ABC, abstractmethod
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any, TypeVar

import httpx
import structlog
from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import sessionmaker

from src.dto.match import MatchDTO
from src.dto.player import PlayerStatDTO
from src.dto.stats import MatchDetailDTO, TeamStatsDTO
from src.models.data_source_log import DataSourceLog
from src.utils.rate_limiter import RateLimitConfig, RateLimiter

logger = structlog.get_logger(__name__)

# Generic param for `_validate_response` — bound to BaseModel so callers get
# a typed instance back, not `Any`.
SchemaT = TypeVar("SchemaT", bound=BaseModel)


class AdapterError(Exception):
    """Base class for adapter-side failures (HTTP, validation, rate-limit)."""


class DataFetchError(AdapterError):
    """Raised when fetching from the upstream source ultimately fails."""

    def __init__(self, source: str, message: str, *, retry_count: int = 0) -> None:
        self.source = source
        self.retry_count = retry_count
        super().__init__(f"[{source}] {message} (retries: {retry_count})")


class AdapterMethodNotSupported(AdapterError):
    """Raised when an adapter method is called on a source that doesn't expose it.

    For example, ``OddsApiAdapter`` only exposes odds, so calling
    ``fetch_team_stats()`` on it should raise this exception rather than
    returning empty / raising NotImplementedError (which would obscure intent).
    """


class BaseDataSourceAdapter(ABC):
    """Abstract base for any external data-source integration.

    Subclasses implement the four ``fetch_*`` abstract methods plus the
    `get_rate_limit()` and `health_check()` hooks. They get retry, rate
    limiting, response validation, and audit logging "for free" via the
    underscore-prefixed helpers below.

    Scraper subclasses additionally override `_get_extra_headers()` (to rotate
    UAs per request) and `_on_blocked()` (to swap proxy + alert on 403). They
    can also extend `_retryable_status` to include 403, since for scrapers
    "blocked" is a transient, retryable condition once the proxy rotates.

    Attributes:
        DEFAULT_TIMEOUT_SECONDS: HTTP request timeout if the subclass does not override it.
        BACKOFF_BASE_SECONDS: Starting wait between retries; doubles each attempt.
        BACKOFF_MAX_SECONDS: Upper cap on the per-retry wait (keeps tail latency bounded).
        DEFAULT_RETRYABLE_STATUS: HTTP statuses to retry by default. 408/425/429
            are transient client-side; 5xx is server-side. Scrapers extend this
            with 403 in their own __init__.
    """

    DEFAULT_TIMEOUT_SECONDS: float = 30.0
    BACKOFF_BASE_SECONDS: float = 1.0
    BACKOFF_MAX_SECONDS: float = 30.0
    DEFAULT_RETRYABLE_STATUS: frozenset[int] = frozenset(
        {408, 425, 429, 500, 502, 503, 504}
    )

    def __init__(
        self,
        source_name: str,
        *,
        rate_limit: RateLimitConfig,
        session_factory: sessionmaker[Any] | None = None,
        base_url: str | None = None,
        timeout: float | None = None,
        default_headers: Mapping[str, str] | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.source_name = source_name
        self._rate_limiter = RateLimiter(rate_limit)
        self._session_factory = session_factory
        self._default_headers: dict[str, str] = dict(default_headers or {})
        self._retryable_status: frozenset[int] = self.DEFAULT_RETRYABLE_STATUS
        self._client = httpx.AsyncClient(
            base_url=base_url or "",
            timeout=timeout if timeout is not None else self.DEFAULT_TIMEOUT_SECONDS,
            transport=transport,
        )
        self._log = logger.bind(adapter=source_name)

    # --- Lifecycle ---

    async def aclose(self) -> None:
        """Release the underlying HTTP client. Call once when done."""
        await self._client.aclose()

    async def __aenter__(self) -> "BaseDataSourceAdapter":
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.aclose()

    # --- Abstract methods (subclasses MUST implement) ---

    @abstractmethod
    async def fetch_matches(self, season_id: str | int) -> list[MatchDTO]:
        """Fetch every match in `season_id` known to this provider."""

    @abstractmethod
    async def fetch_match_detail(self, match_id: str | int) -> MatchDetailDTO:
        """Fetch full details (stats + lineups + odds where available) for one match."""

    @abstractmethod
    async def fetch_team_stats(
        self, team_id: str | int, season_id: str | int
    ) -> TeamStatsDTO:
        """Fetch a team's season-to-date aggregate stats."""

    @abstractmethod
    async def fetch_player_stats(self, match_id: str | int) -> list[PlayerStatDTO]:
        """Fetch per-player stat lines for a single match."""

    @abstractmethod
    def get_rate_limit(self) -> RateLimitConfig:
        """Return the provider's documented rate limit (used for sanity checks)."""

    @abstractmethod
    async def health_check(self) -> bool:
        """Lightweight ping that returns True iff the provider is reachable."""

    # --- Extension hooks (subclasses MAY override) ---

    def _get_extra_headers(self) -> dict[str, str]:
        """Headers to merge on top of `default_headers` for each request.

        Default returns an empty dict. Scrapers override this to inject a
        freshly-rotated User-Agent on every request.
        """
        return {}

    async def _on_blocked(self, response: httpx.Response) -> None:
        """Hook fired when a retryable block status (e.g. 403) is observed.

        The default implementation is a no-op (the retry loop just retries).
        Scrapers override this to alert + swap proxy before the retry.
        """
        return None

    # --- Shared helpers (subclasses USE) ---

    async def _request_with_retry(
        self,
        url: str,
        *,
        params: Mapping[str, str | int] | None = None,
        headers: Mapping[str, str] | None = None,
        max_retries: int = 3,
    ) -> httpx.Response:
        """GET `url` with rate limiting, exponential backoff, and 4xx-aware retry.

        Args:
            url: Absolute URL or path (resolved against the adapter's `base_url`).
            params: Query parameters.
            headers: Per-request headers; merged on top of default + extra hooks.
            max_retries: Max attempts after the initial request fails.

        Raises:
            DataFetchError: After `max_retries` retryable failures, or on the
                first non-retryable HTTP status.
        """
        merged_headers = self._merge_headers(headers)
        last_exc: Exception | None = None
        for attempt in range(max_retries + 1):
            await self._rate_limiter.acquire()
            response, exc = await self._do_request(url, params, merged_headers)

            if exc is not None:
                last_exc = exc
                self._log.warning(
                    "request_transport_error", url=url, attempt=attempt, error=str(exc)
                )
            elif response is not None and response.status_code < 400:
                return response
            elif response is not None:
                if response.status_code not in self._retryable_status:
                    raise DataFetchError(
                        self.source_name,
                        f"HTTP {response.status_code} (non-retryable) for {url}",
                        retry_count=attempt,
                    )
                last_exc = httpx.HTTPStatusError(
                    f"HTTP {response.status_code}",
                    request=response.request,
                    response=response,
                )
                self._log.warning(
                    "request_retryable_status",
                    url=url,
                    attempt=attempt,
                    status=response.status_code,
                )
                # 403 means "blocked" for scrapers; let the hook swap proxy.
                if response.status_code == 403:
                    await self._on_blocked(response)

            if attempt < max_retries:
                await self._sleep_backoff(attempt)

        raise DataFetchError(
            self.source_name,
            f"Exhausted retries for {url}: {last_exc}",
            retry_count=max_retries,
        )

    def _validate_response(self, data: object, schema: type[SchemaT]) -> SchemaT:
        """Validate raw JSON-ish data against a Pydantic schema, raising on failure.

        Args:
            data: Parsed JSON (dict / list / scalar).
            schema: Concrete Pydantic model type.

        Returns:
            A typed instance of `schema`.

        Raises:
            DataFetchError: When validation fails (caller should treat as a
                fatal upstream-format change rather than a transient blip).
        """
        try:
            return schema.model_validate(data)
        except ValidationError as exc:
            self._log.error("response_validation_failed", schema=schema.__name__, error=str(exc))
            raise DataFetchError(
                self.source_name, f"Response failed {schema.__name__} validation: {exc}"
            ) from exc

    async def _log_operation(
        self,
        task_type: str,
        status: str,
        *,
        started_at: datetime,
        finished_at: datetime | None = None,
        records_fetched: int | None = None,
        records_inserted: int | None = None,
        records_updated: int | None = None,
        error_message: str | None = None,
        meta: dict[str, Any] | None = None,
    ) -> None:
        """Persist a row in `data_source_logs` for this run.

        Silently no-ops when no `session_factory` was injected (useful in unit
        tests that don't have a DB).
        """
        if self._session_factory is None:
            return

        finished = finished_at or datetime.now(timezone.utc)
        with self._session_factory() as session:
            session.add(
                DataSourceLog(
                    source_name=self.source_name,
                    task_type=task_type,
                    status=status,
                    records_fetched=records_fetched,
                    records_inserted=records_inserted,
                    records_updated=records_updated,
                    error_message=error_message,
                    started_at=started_at,
                    finished_at=finished,
                    meta=meta,
                )
            )
            session.commit()

    async def _respect_rate_limit(self) -> None:
        """Public-style alias for callers that want pacing without a request."""
        await self._rate_limiter.acquire()

    # --- Private helpers ---

    def _merge_headers(self, per_call: Mapping[str, str] | None) -> dict[str, str]:
        return {**self._default_headers, **self._get_extra_headers(), **dict(per_call or {})}

    async def _do_request(
        self,
        url: str,
        params: Mapping[str, str | int] | None,
        headers: Mapping[str, str],
    ) -> tuple[httpx.Response | None, Exception | None]:
        try:
            response = await self._client.get(url, params=params, headers=headers)
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            return None, exc
        return response, None

    async def _sleep_backoff(self, attempt: int) -> None:
        # Exponential backoff with full jitter (AWS architecture blog).
        cap = min(self.BACKOFF_BASE_SECONDS * (2**attempt), self.BACKOFF_MAX_SECONDS)
        await asyncio.sleep(random.uniform(0.0, cap))

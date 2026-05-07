"""Custom FastAPI middlewares: API-key auth, rate limiting, request logging.

`APIKeyMiddleware` enforces a static `X-API-Key` header against
`settings.API_KEY`. When the setting is empty, auth is bypassed (useful for
local dev / tests). Health-check paths are always allowed.

`RateLimitMiddleware` is a sliding-window counter keyed on the client IP. It
uses a small in-process LRU; production deployments running multiple replicas
should swap in a Redis-backed limiter (Phase 3 deliverable).

`AccessLogMiddleware` logs one structured line per request, complete with
request id, latency, and outcome.
"""
from __future__ import annotations

import time
import uuid
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable
from typing import Final

import structlog
from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from src.config.settings import settings

logger = structlog.get_logger(__name__)

_PUBLIC_PATHS: Final[frozenset[str]] = frozenset(
    {
        "/api/v1/model/health",
        "/health",
        "/",
        "/docs",
        "/redoc",
        "/openapi.json",
        # Browser error reporting — must accept anonymous fire-and-forget POSTs
        # so the public `error.tsx` boundary can phone home with the digest.
        "/api/v1/client-errors",
        # Live USD↔CNY rate — public, used by the subscribe page on every load.
        "/api/v1/fx/usd-cny",
    }
)


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Reject requests whose `X-API-Key` header doesn't match the configured key."""

    HEADER: Final[str] = "X-API-Key"

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if not settings.API_KEY or _is_public(request.url.path):
            return await call_next(request)

        provided = request.headers.get(self.HEADER)
        if provided != settings.API_KEY:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "code": 40101,
                    "error": "INVALID_API_KEY",
                    "message": "Missing or invalid X-API-Key header.",
                },
            )
        return await call_next(request)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding-window per-IP rate limiter. Window is fixed at 60 s."""

    WINDOW_SECONDS: Final[float] = 60.0

    def __init__(self, app, requests_per_minute: int) -> None:  # type: ignore[no-untyped-def]
        super().__init__(app)
        self._budget = max(requests_per_minute, 1)
        # client_ip -> deque of timestamps within the window
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if _is_public(request.url.path):
            return await call_next(request)

        client_ip = _client_ip(request)
        now = time.monotonic()
        window_start = now - self.WINDOW_SECONDS

        hits = self._hits[client_ip]
        # Trim entries older than the window.
        while hits and hits[0] < window_start:
            hits.popleft()
        if len(hits) >= self._budget:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "code": 42901,
                    "error": "RATE_LIMITED",
                    "message": f"Too many requests; budget is {self._budget}/min.",
                },
            )
        hits.append(now)

        return await call_next(request)


class AccessLogMiddleware(BaseHTTPMiddleware):
    """Emit one structured log line per request: id + path + status + latency."""

    HEADER_REQUEST_ID: Final[str] = "X-Request-Id"

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = request.headers.get(self.HEADER_REQUEST_ID) or uuid.uuid4().hex
        start = time.perf_counter()
        response: Response | None = None
        try:
            response = await call_next(request)
            return response
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            status_code = response.status_code if response is not None else 500
            logger.info(
                "api_request",
                method=request.method,
                path=request.url.path,
                status=status_code,
                latency_ms=round(elapsed_ms, 2),
                request_id=request_id,
                client_ip=_client_ip(request),
            )
            if response is not None:
                response.headers[self.HEADER_REQUEST_ID] = request_id


# --- Helpers ---


def _is_public(path: str) -> bool:
    return path in _PUBLIC_PATHS


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client is not None:
        return request.client.host
    return "unknown"

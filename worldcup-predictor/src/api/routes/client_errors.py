"""POST /api/v1/client-errors — fire-and-forget browser error sentinel.

The Next.js `error.tsx` boundary surfaces a digest to the user; we want
that digest, the pathname, and the user-agent on the server side too so a
support ping can be cross-referenced against backend logs without setting
up an external service like Sentry.

Stores nothing yet — just emits a structlog event tagged
``client_error_reported``. Operators can grep server logs by digest.
"""
from __future__ import annotations

import structlog
from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/v1", tags=["client-errors"])


class ClientErrorIn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    digest: str | None = Field(default=None, max_length=128)
    pathname: str | None = Field(default=None, max_length=500)
    message: str | None = Field(default=None, max_length=2000)


@router.post("/client-errors")
def log_client_error(payload: ClientErrorIn, request: Request) -> dict[str, str]:
    """Log a browser-side error. Always returns 200 — never blocks the UI."""
    user_agent = request.headers.get("user-agent", "?")
    client_ip = request.client.host if request.client else "?"
    logger.info(
        "client_error_reported",
        digest=payload.digest,
        pathname=payload.pathname,
        message=payload.message,
        user_agent=user_agent,
        client_ip=client_ip,
    )
    return {"status": "logged"}

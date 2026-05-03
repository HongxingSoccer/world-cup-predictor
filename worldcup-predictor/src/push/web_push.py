"""Web Push (VAPID) notifier implementation."""
from __future__ import annotations

import json
from typing import Optional

import structlog

from src.push.base import DeliveryResult, NotificationPayload

logger = structlog.get_logger(__name__)


class WebPushNotifier:
    """VAPID-authenticated Web Push delivery via :mod:`pywebpush`."""

    channel: str = "web_push"

    def __init__(
        self,
        *,
        vapid_private_key: str,
        vapid_claims_email: str,
        ttl_seconds: int = 3600,
    ) -> None:
        if not vapid_private_key:
            raise ValueError("vapid_private_key is required")
        if not vapid_claims_email or "@" not in vapid_claims_email:
            raise ValueError("vapid_claims_email must be a valid mailto address")
        self._private_key = vapid_private_key
        self._claims_email = vapid_claims_email
        self._ttl = ttl_seconds

    def send(
        self, *, recipient: str, payload: NotificationPayload
    ) -> DeliveryResult:
        """Send one push; ``recipient`` is a JSON-encoded subscription info."""
        try:
            subscription = json.loads(recipient)
        except (TypeError, ValueError) as exc:
            return DeliveryResult(self.channel, False, f"invalid subscription: {exc}")

        body = json.dumps(_payload_to_dict(payload), ensure_ascii=False)
        return _do_webpush(
            subscription=subscription,
            data=body,
            private_key=self._private_key,
            claims_email=self._claims_email,
            ttl=self._ttl,
            channel=self.channel,
        )


def _payload_to_dict(payload: NotificationPayload) -> dict:
    return {
        "title": payload.title,
        "body": payload.body,
        "kind": payload.kind.value,
        "deep_link": payload.deep_link,
        "data": payload.data,
    }


def _do_webpush(
    *,
    subscription: dict,
    data: str,
    private_key: str,
    claims_email: str,
    ttl: int,
    channel: str,
) -> DeliveryResult:
    """Thin wrapper around :func:`pywebpush.webpush` with library-level errors trapped."""
    try:
        from pywebpush import WebPushException, webpush  # noqa: WPS433
    except ImportError:
        return DeliveryResult(channel, False, "pywebpush not installed")
    try:
        response = webpush(
            subscription_info=subscription,
            data=data,
            vapid_private_key=private_key,
            vapid_claims={"sub": f"mailto:{claims_email}"},
            ttl=ttl,
        )
        message_id: Optional[str] = response.headers.get("Location") if hasattr(response, "headers") else None
        return DeliveryResult(channel, True, provider_message_id=message_id)
    except WebPushException as exc:  # type: ignore[misc]
        return DeliveryResult(channel, False, str(exc))

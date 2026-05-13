"""Stub notifiers for mobile + WeChat channels.

These will become real implementations once:

  * APNs — Apple developer account is set up and the iOS app reaches
    TestFlight. Needs a .p8 auth key + bundle ID + APNs cert.
  * FCM  — Firebase project is provisioned. Needs a service-account JSON
    + the FCM credentials env var.
  * WeChat OA — the official-account application clears verification.
    Needs the AppID + AppSecret + a template-message ID.

Until then every call logs and returns ``False`` so the caller can treat
the channel as inactive without crashing. The DB-write side of every
notification path still fires, so users see the alert in the in-app
notification centre even with all of these stubbed.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def send_apns_stub(user_id: int, title: str, body: str, payload: dict[str, Any]) -> bool:
    """TODO(apns): real implementation requires Apple .p8 + bundle ID."""
    logger.info(
        "apns_stub", extra={"user_id": user_id, "title": title, "kind": "stub"}
    )
    return False


def send_fcm_stub(user_id: int, title: str, body: str, payload: dict[str, Any]) -> bool:
    """TODO(fcm): real implementation requires Firebase service-account JSON."""
    logger.info(
        "fcm_stub", extra={"user_id": user_id, "title": title, "kind": "stub"}
    )
    return False


def send_wechat_stub(openid: str, title: str, body: str, payload: dict[str, Any]) -> bool:
    """TODO(wechat): real implementation requires verified OA + template ID."""
    logger.info(
        "wechat_stub",
        extra={"openid_prefix": openid[:6] + "…", "title": title, "kind": "stub"},
    )
    return False


def send_email_stub(user_id: int, title: str, body: str) -> bool:
    """TODO(email): wire up Mailgun / SES once the marketing flow needs it."""
    logger.info(
        "email_stub", extra={"user_id": user_id, "title": title, "kind": "stub"}
    )
    return False


__all__ = [
    "send_apns_stub",
    "send_fcm_stub",
    "send_wechat_stub",
    "send_email_stub",
]

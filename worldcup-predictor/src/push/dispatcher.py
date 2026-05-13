"""High-level dispatcher for M9.5 + M10 notifications.

Two responsibilities:

1. **Persist** — every notification, whatever the channel, is recorded in
   ``push_notifications`` so the in-app notification centre always has
   it. Even if every external channel is misconfigured, the user can
   still see the alert next time they open the bell.

2. **Fan out** — for each channel the user has opted into, hand the
   payload to the matching notifier. Web push is the only channel with
   a real implementation today; APNs / FCM / wechat / email all live as
   ``send_stub`` functions in :mod:`src.push.stubs` and just log.

Errors in any single channel never block the others — the persistence
write is the load-bearing one, and we don't retry inline.
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from src.models.push import PushNotification, UserPushSettings
from src.models.user_position import UserPosition
from src.push.base import NotificationKind
from src.push.stubs import send_apns_stub, send_fcm_stub, send_wechat_stub

logger = logging.getLogger(__name__)


class NotificationDispatcher:
    """Static-method dispatcher; thread-safe."""

    # ------------------------------------------------------------------
    # M9.5 — hedge-window alert
    # ------------------------------------------------------------------

    @staticmethod
    def send_hedge_window_alert(
        session: Session,
        position: UserPosition,
        opportunity: dict[str, Any],
    ) -> PushNotification:
        """Send the "your position has a hedge window open" alert.

        ``opportunity`` is the dict shape returned by
        :class:`HedgeOpportunityDetector.detect`.
        """
        title = "对冲窗口打开"
        body = (
            f"{position.platform} · 您的下注现在可对冲。"
            f"推荐对冲方向: {opportunity.get('recommended_hedge_outcome')}, "
            f"赔率 {opportunity.get('recommended_hedge_odds')}"
        )

        return NotificationDispatcher._dispatch(
            session=session,
            user_id=position.user_id,
            kind=NotificationKind.HEDGE_WINDOW,
            title=title,
            body=body,
            position_id=position.id,
            match_id=position.match_id,
            payload={
                "trigger_reason": opportunity.get("trigger_reason"),
                "recommended_hedge_outcome": opportunity.get(
                    "recommended_hedge_outcome"
                ),
                "recommended_hedge_odds": _as_float(
                    opportunity.get("recommended_hedge_odds")
                ),
                "recommended_hedge_stake": _as_float(
                    opportunity.get("recommended_hedge_stake")
                ),
                "best_bookmaker": opportunity.get("best_bookmaker"),
                "model_assessment": opportunity.get("model_assessment"),
            },
            target_url=f"/hedge?from_position={position.id}",
        )

    # ------------------------------------------------------------------
    # M9.5 — position settled
    # ------------------------------------------------------------------

    @staticmethod
    def send_position_settled(
        session: Session, position: UserPosition
    ) -> PushNotification:
        pnl = position.settlement_pnl or 0
        title = (
            "持仓已结算 · 盈利" if pnl >= 0 else "持仓已结算 · 亏损"
        )
        body = f"{position.platform} · {position.market} · 盈亏: ¥{pnl}"
        return NotificationDispatcher._dispatch(
            session=session,
            user_id=position.user_id,
            kind=NotificationKind.POSITION_SETTLED,
            title=title,
            body=body,
            position_id=position.id,
            match_id=position.match_id,
            payload={"settlement_pnl": _as_float(pnl)},
            target_url=f"/positions",
        )

    # ------------------------------------------------------------------
    # M10 — arbitrage window (placeholder; signature stable for the
    # arbitrage worker to call once M10 lands).
    # ------------------------------------------------------------------

    @staticmethod
    def send_arb_alert(
        session: Session,
        user_id: int,
        title: str,
        body: str,
        match_id: int | None,
        payload: dict[str, Any],
    ) -> PushNotification:
        return NotificationDispatcher._dispatch(
            session=session,
            user_id=user_id,
            kind=NotificationKind.HIGH_EV,  # reuse until "arb" kind ships
            title=title,
            body=body,
            position_id=None,
            match_id=match_id,
            payload=payload,
            target_url="/arbitrage",
        )

    # ------------------------------------------------------------------
    # Internal — persist + fan out
    # ------------------------------------------------------------------

    @staticmethod
    def _dispatch(
        *,
        session: Session,
        user_id: int,
        kind: NotificationKind,
        title: str,
        body: str,
        position_id: int | None,
        match_id: int | None,
        payload: dict[str, Any],
        target_url: str | None,
    ) -> PushNotification:
        notification = PushNotification(
            user_id=user_id,
            channel="db",  # always; external delivery is logged separately
            notification_type=str(kind),
            title=title,
            body=body,
            target_url=target_url,
            position_id=position_id,
            match_id=match_id,
            status="pending",
            meta=payload,
        )
        session.add(notification)
        session.flush()

        # Channels — only kick off ones the user has explicitly opted into.
        settings = (
            session.query(UserPushSettings)
            .filter(UserPushSettings.user_id == user_id)
            .one_or_none()
        )
        kind_str = str(kind)
        wanted = NotificationDispatcher._channels_for(settings, kind_str)

        delivered_any = False
        if "web_push" in wanted and settings and settings.web_push_subscription:
            delivered_any |= _send_web_push(
                settings.web_push_subscription, title, body, payload, target_url
            )
        if "apns" in wanted:
            delivered_any |= send_apns_stub(user_id, title, body, payload)
        if "fcm" in wanted:
            delivered_any |= send_fcm_stub(user_id, title, body, payload)
        if "wechat" in wanted and settings and settings.wechat_openid:
            delivered_any |= send_wechat_stub(
                settings.wechat_openid, title, body, payload
            )

        # The DB row is always "sent" — the user can read it from the
        # notification centre even when every external channel failed.
        notification.status = "sent" if delivered_any else "sent_db_only"
        session.commit()
        return notification

    @staticmethod
    def _channels_for(
        settings: UserPushSettings | None, kind: str
    ) -> set[str]:
        # Default: all channels enabled. Settings rows are sparse — only
        # populated for users who've customised. A missing row means
        # "send everywhere I can".
        all_channels = {"web_push", "apns", "fcm", "wechat"}
        if settings is None:
            return all_channels
        # Honour the per-kind feature flags carried on UserPushSettings.
        flag_attr = {
            "high_ev": "enable_high_ev",
            "report": "enable_reports",
            "match_start": "enable_match_start",
            "red_hit": "enable_red_hit",
            # M9.5 kinds default-on; user disables explicitly via the
            # settings page (UI surfaced in the notifications drawer).
            "hedge_window": "enable_match_start",
            "position_settled": "enable_red_hit",
        }.get(kind)
        if flag_attr and not getattr(settings, flag_attr, True):
            return set()
        return all_channels


# --------------------------------------------------------------------------
# Web push glue
# --------------------------------------------------------------------------


def _send_web_push(
    subscription: dict,
    title: str,
    body: str,
    payload: dict,
    target_url: str | None,
) -> bool:
    """Best-effort web-push send. Returns True on success, False on any
    error — caller surfaces success-on-DB only."""
    try:
        from src.config.settings import settings as app_settings

        vapid_key = getattr(app_settings, "VAPID_PRIVATE_KEY", "") or ""
        vapid_email = getattr(app_settings, "VAPID_CLAIMS_EMAIL", "") or ""
        if not vapid_key or not vapid_email:
            logger.info(
                "web_push_skipped_vapid_not_configured",
                extra={"reason": "vapid_keys_missing"},
            )
            return False
        from src.push.web_push import WebPushNotifier  # local import — heavy dep

        notifier = WebPushNotifier(
            vapid_private_key=vapid_key,
            vapid_claims_email=vapid_email,
        )
        from src.push.base import NotificationPayload

        result = notifier.send(
            recipient=subscription,  # type: ignore[arg-type]
            payload=NotificationPayload(
                kind=NotificationKind.HEDGE_WINDOW,
                title=title,
                body=body,
                deep_link=target_url,
                data=payload,
            ),
        )
        return bool(result.success)
    except Exception as exc:  # noqa: BLE001 — defensive
        logger.warning("web_push_failed", extra={"error": str(exc)})
        return False


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


__all__ = ["NotificationDispatcher"]

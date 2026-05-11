"""WeChat Mini Program template-message notifier."""
from __future__ import annotations

from typing import Any

import httpx
import structlog

from src.push.base import DeliveryResult, NotificationPayload

logger = structlog.get_logger(__name__)

WECHAT_TOKEN_URL = "https://api.weixin.qq.com/cgi-bin/token"
WECHAT_SUBSCRIBE_SEND_URL = (
    "https://api.weixin.qq.com/cgi-bin/message/subscribe/send"
)


class WeChatNotifier:
    """Sends a subscribe-message via the WeChat MP API.

    Recipient is the user's ``openid``. Access tokens are fetched lazily via
    the injected :class:`httpx.Client` and cached in-memory; production
    deployments should swap this for a Redis-backed cache because tokens are
    issued globally per appid.
    """

    channel: str = "wechat"

    def __init__(
        self,
        *,
        appid: str,
        secret: str,
        template_id: str,
        http_client: httpx.Client | None = None,
    ) -> None:
        if not appid or not secret or not template_id:
            raise ValueError("appid / secret / template_id are required")
        self._appid = appid
        self._secret = secret
        self._template_id = template_id
        self._client = http_client or httpx.Client(timeout=10.0)
        self._cached_token: str | None = None

    def send(
        self, *, recipient: str, payload: NotificationPayload
    ) -> DeliveryResult:
        token = self._access_token()
        if token is None:
            return DeliveryResult(self.channel, False, "failed to fetch access token")
        body = _build_subscribe_message(
            openid=recipient,
            template_id=self._template_id,
            payload=payload,
        )
        return _post_subscribe(self._client, token, body, self.channel)

    def _access_token(self) -> str | None:
        if self._cached_token:
            return self._cached_token
        try:
            resp = self._client.get(
                WECHAT_TOKEN_URL,
                params={
                    "grant_type": "client_credential",
                    "appid": self._appid,
                    "secret": self._secret,
                },
            )
            data = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("wechat_token_fetch_failed", error=str(exc))
            return None
        token = data.get("access_token")
        if isinstance(token, str) and token:
            self._cached_token = token
            return token
        return None


def _build_subscribe_message(
    *, openid: str, template_id: str, payload: NotificationPayload
) -> dict[str, Any]:
    return {
        "touser": openid,
        "template_id": template_id,
        "page": payload.deep_link or "pages/index/index",
        "data": {
            "thing1": {"value": payload.title[:20]},
            "thing2": {"value": payload.body[:20]},
        },
    }


def _post_subscribe(
    client: httpx.Client, access_token: str, body: dict, channel: str
) -> DeliveryResult:
    try:
        resp = client.post(
            WECHAT_SUBSCRIBE_SEND_URL,
            params={"access_token": access_token},
            json=body,
        )
        data = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        return DeliveryResult(channel, False, f"http error: {exc}")
    if data.get("errcode") == 0:
        return DeliveryResult(channel, True, provider_message_id=str(data.get("msgid", "")))
    return DeliveryResult(channel, False, f"wechat error: {data}")

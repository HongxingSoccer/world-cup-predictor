"""SMTP email notifier — last-resort fallback channel."""
from __future__ import annotations

import smtplib
from email.message import EmailMessage

import structlog

from src.push.base import DeliveryResult, NotificationPayload

logger = structlog.get_logger(__name__)


class EmailNotifier:
    """Plain SMTP notifier; ``recipient`` is an email address."""

    channel: str = "email"

    def __init__(
        self,
        *,
        smtp_host: str,
        smtp_port: int,
        username: str,
        password: str,
        from_address: str,
        use_tls: bool = True,
    ) -> None:
        if not smtp_host or not from_address:
            raise ValueError("smtp_host and from_address are required")
        self._host = smtp_host
        self._port = smtp_port
        self._username = username
        self._password = password
        self._from_address = from_address
        self._use_tls = use_tls

    def send(
        self, *, recipient: str, payload: NotificationPayload
    ) -> DeliveryResult:
        message = _build_message(
            to_address=recipient,
            from_address=self._from_address,
            payload=payload,
        )
        return _send_smtp(
            message=message,
            host=self._host,
            port=self._port,
            username=self._username,
            password=self._password,
            use_tls=self._use_tls,
            channel=self.channel,
        )


def _build_message(
    *, to_address: str, from_address: str, payload: NotificationPayload
) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = from_address
    msg["To"] = to_address
    msg["Subject"] = payload.title
    body = payload.body
    if payload.deep_link:
        body = f"{body}\n\n查看详情：{payload.deep_link}"
    msg.set_content(body)
    return msg


def _send_smtp(
    *,
    message: EmailMessage,
    host: str,
    port: int,
    username: str,
    password: str,
    use_tls: bool,
    channel: str,
) -> DeliveryResult:
    try:
        with smtplib.SMTP(host, port, timeout=10) as smtp:
            smtp.ehlo()
            if use_tls:
                smtp.starttls()
                smtp.ehlo()
            if username:
                smtp.login(username, password)
            smtp.send_message(message)
        return DeliveryResult(channel, True)
    except (smtplib.SMTPException, OSError) as exc:
        return DeliveryResult(channel, False, str(exc))

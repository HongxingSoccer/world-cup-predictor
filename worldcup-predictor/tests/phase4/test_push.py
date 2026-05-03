"""Unit tests for src.push.* (notifier abstraction + dispatcher)."""
from __future__ import annotations

import pytest

from src.push.base import (
    DeliveryResult,
    NotificationKind,
    NotificationPayload,
    PushDispatcher,
    RateLimitPolicy,
)


class _FakeNotifier:
    def __init__(self, channel: str, *, fail: bool = False) -> None:
        self.channel = channel
        self.fail = fail
        self.calls: list[tuple[str, NotificationPayload]] = []

    def send(self, *, recipient: str, payload: NotificationPayload) -> DeliveryResult:
        self.calls.append((recipient, payload))
        if self.fail:
            raise RuntimeError("simulated failure")
        return DeliveryResult(self.channel, True, provider_message_id="msg-1")


def _payload(kind: NotificationKind = NotificationKind.RED_HIT) -> NotificationPayload:
    return NotificationPayload(
        kind=kind,
        title="红单命中",
        body="阿根廷 vs 法国 主胜命中",
        deep_link="/predictions/123",
    )


def test_dispatcher_fans_out_to_each_channel():
    a = _FakeNotifier("web_push")
    b = _FakeNotifier("email")
    disp = PushDispatcher([a, b])
    results = disp.dispatch(
        user_id=1,
        recipients_by_channel={"web_push": "sub-1", "email": "user@example.com"},
        payload=_payload(),
    )
    assert len(results) == 2
    assert all(r.success for r in results)
    assert len(a.calls) == 1 and len(b.calls) == 1


def test_dispatcher_skips_channels_not_enabled():
    a = _FakeNotifier("web_push")
    b = _FakeNotifier("email")
    disp = PushDispatcher([a, b])
    results = disp.dispatch(
        user_id=1,
        recipients_by_channel={"web_push": "sub-1", "email": "u@e.com"},
        payload=_payload(),
        enabled_channels={"email"},
    )
    assert len(results) == 1
    assert results[0].channel == "email"
    assert len(a.calls) == 0


def test_dispatcher_records_failure_without_raising():
    bad = _FakeNotifier("wechat", fail=True)
    disp = PushDispatcher([bad])
    results = disp.dispatch(
        user_id=1,
        recipients_by_channel={"wechat": "openid-1"},
        payload=_payload(),
    )
    assert results[0].success is False
    assert "simulated failure" in (results[0].error or "")


def test_dispatcher_unknown_channel_returns_failure():
    a = _FakeNotifier("web_push")
    disp = PushDispatcher([a])
    results = disp.dispatch(
        user_id=1,
        recipients_by_channel={"sms": "+861234"},
        payload=_payload(),
    )
    assert results[0].success is False
    assert results[0].channel == "sms"


def test_dispatcher_rejects_duplicate_channels():
    a = _FakeNotifier("email")
    b = _FakeNotifier("email")
    with pytest.raises(ValueError):
        PushDispatcher([a, b])


def test_dispatcher_requires_at_least_one_notifier():
    with pytest.raises(ValueError):
        PushDispatcher([])

"""Notifier abstraction + dispatcher + rate-limit/quiet-hours helpers (Phase 4).

The notification subsystem follows ``docs/design/06_Phase4_ModelEvolution.md
§5``. Five scenarios drive every push:

* ``HIGH_EV``       — model finds a ⭐⭐⭐ value signal (paid-tier only).
* ``REPORT``        — AI 赛前报告 published.
* ``MATCH_START``   — favourited match kicks off in 30 min.
* ``RED_HIT``       — settlement reported a winning prediction.
* ``MILESTONE``     — connected wins / new ROI high (marketing fan-out).

A :class:`Notifier` knows how to deliver one notification through a single
channel (web push, WeChat MP template message, email, app push). The
:class:`PushDispatcher` fans a payload out to every notifier whose channel
matches a user preference. :class:`RateLimitPolicy` enforces the per-day
caps + immediate-dedup + quiet-hours rules from §5.4.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, time, timezone
from enum import Enum
from typing import Iterable, Optional, Protocol

import structlog

logger = structlog.get_logger(__name__)


class NotificationKind(str, Enum):
    """High-level notification trigger (matches design §5.1 verbatim)."""

    HIGH_EV = "high_ev"
    REPORT = "report"
    MATCH_START = "match_start"
    RED_HIT = "red_hit"
    MILESTONE = "milestone"


# Per-day caps from design §5.4.
DEFAULT_DAILY_CAP: int = 5
PER_KIND_DAILY_CAP: dict[NotificationKind, int] = {
    NotificationKind.HIGH_EV: 3,
}


@dataclass(frozen=True)
class NotificationPayload:
    """Channel-agnostic message body. Notifiers translate to their format."""

    kind: NotificationKind
    title: str
    body: str
    deep_link: Optional[str] = None
    target_id: Optional[str] = None  # used for dedup (e.g. "match:42")
    data: dict = field(default_factory=dict)


@dataclass(frozen=True)
class DeliveryResult:
    """Outcome of one ``Notifier.send`` call. ``error`` is None on success."""

    channel: str
    success: bool
    error: Optional[str] = None
    provider_message_id: Optional[str] = None
    skipped_reason: Optional[str] = None  # populated when policy blocks delivery


class Notifier(Protocol):
    """One push channel. Implementations are stateless / thread-safe."""

    channel: str

    def send(
        self, *, recipient: str, payload: NotificationPayload
    ) -> DeliveryResult:
        """Deliver one message; returns a :class:`DeliveryResult`."""


# ---------------------------------------------------------------------------
# Rate limit / quiet hours / dedup
# ---------------------------------------------------------------------------


@dataclass
class RateLimitPolicy:
    """In-memory rate limiter. Production uses Redis with the same contract."""

    daily_cap: int = DEFAULT_DAILY_CAP
    per_kind_cap: dict[NotificationKind, int] = field(
        default_factory=lambda: dict(PER_KIND_DAILY_CAP)
    )
    quiet_start: Optional[time] = None  # local time (24h) inclusive
    quiet_end: Optional[time] = None  # exclusive
    _per_user_day: dict[tuple[int, str], int] = field(default_factory=lambda: defaultdict(int))
    _per_user_kind_day: dict[tuple[int, str, str], int] = field(default_factory=lambda: defaultdict(int))
    _seen_targets: set[tuple[int, str, str]] = field(default_factory=set)

    def check(
        self,
        *,
        user_id: int,
        payload: NotificationPayload,
        now: Optional[datetime] = None,
    ) -> Optional[str]:
        """Return ``None`` if delivery is allowed, else a reason string."""
        now = now or datetime.now(timezone.utc)
        day_key = now.date().isoformat()

        if payload.target_id is not None:
            dedup_key = (user_id, payload.kind.value, payload.target_id)
            if dedup_key in self._seen_targets:
                return "duplicate"

        if self._per_user_day[(user_id, day_key)] >= self.daily_cap:
            return "daily_cap"

        kind_cap = self.per_kind_cap.get(payload.kind)
        if kind_cap is not None and (
            self._per_user_kind_day[(user_id, payload.kind.value, day_key)] >= kind_cap
        ):
            return "kind_cap"

        if self._in_quiet_hours(now):
            return "quiet_hours"
        return None

    def record(
        self,
        *,
        user_id: int,
        payload: NotificationPayload,
        now: Optional[datetime] = None,
    ) -> None:
        """Increment counters after a *successful* dispatch."""
        now = now or datetime.now(timezone.utc)
        day_key = now.date().isoformat()
        self._per_user_day[(user_id, day_key)] += 1
        self._per_user_kind_day[(user_id, payload.kind.value, day_key)] += 1
        if payload.target_id is not None:
            self._seen_targets.add((user_id, payload.kind.value, payload.target_id))

    def _in_quiet_hours(self, now: datetime) -> bool:
        if self.quiet_start is None or self.quiet_end is None:
            return False
        t = now.timetz().replace(tzinfo=None)
        if self.quiet_start <= self.quiet_end:
            return self.quiet_start <= t < self.quiet_end
        # Wraps midnight (e.g. 22:00 → 07:00)
        return t >= self.quiet_start or t < self.quiet_end


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------


class PushDispatcher:
    """Fan a payload out to every notifier whose channel is enabled."""

    def __init__(
        self,
        notifiers: Iterable[Notifier],
        *,
        rate_limit: Optional[RateLimitPolicy] = None,
    ) -> None:
        notifiers = list(notifiers)
        if not notifiers:
            raise ValueError("dispatcher requires at least one notifier")
        seen: set[str] = set()
        for n in notifiers:
            if n.channel in seen:
                raise ValueError(f"duplicate channel {n.channel!r}")
            seen.add(n.channel)
        self._notifiers = {n.channel: n for n in notifiers}
        self._rate_limit = rate_limit

    def dispatch(
        self,
        *,
        user_id: int,
        recipients_by_channel: dict[str, str],
        payload: NotificationPayload,
        enabled_channels: Optional[set[str]] = None,
    ) -> list[DeliveryResult]:
        """Send ``payload`` to each ``(channel, recipient)`` pair allowed."""
        if self._rate_limit is not None:
            blocked = self._rate_limit.check(user_id=user_id, payload=payload)
            if blocked is not None:
                logger.info(
                    "push_blocked_by_policy",
                    user_id=user_id,
                    kind=payload.kind.value,
                    reason=blocked,
                )
                return [
                    DeliveryResult(
                        channel=ch,
                        success=False,
                        skipped_reason=blocked,
                    )
                    for ch in recipients_by_channel
                    if enabled_channels is None or ch in enabled_channels
                ]

        results: list[DeliveryResult] = []
        for channel, recipient in recipients_by_channel.items():
            if enabled_channels is not None and channel not in enabled_channels:
                continue
            notifier = self._notifiers.get(channel)
            if notifier is None:
                results.append(
                    DeliveryResult(channel, False, f"no notifier for {channel}")
                )
                continue
            results.append(_safe_send(notifier, recipient, payload))

        if self._rate_limit is not None and any(r.success for r in results):
            self._rate_limit.record(user_id=user_id, payload=payload)
        return results


def _safe_send(
    notifier: Notifier, recipient: str, payload: NotificationPayload
) -> DeliveryResult:
    """Wrap ``notifier.send`` so a single channel failure doesn't poison the batch."""
    try:
        return notifier.send(recipient=recipient, payload=payload)
    except Exception as exc:  # noqa: BLE001 — channel boundary, log + continue
        logger.warning(
            "notifier_failed",
            channel=notifier.channel,
            error=str(exc),
            kind=payload.kind.value,
        )
        return DeliveryResult(notifier.channel, False, str(exc))

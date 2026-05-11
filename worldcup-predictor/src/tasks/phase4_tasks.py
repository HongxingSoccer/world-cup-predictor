"""Celery tasks for Phase 4 (AI reports, Monte Carlo, push fan-out).

Three task families that all conform to ``docs/design/06_Phase4_ModelEvolution.md``:

* :func:`generate_match_report` — calls the LLM once per ``match_id`` and
  upserts ``analysis_reports`` (one *published* row per match, see §4.5).
* :func:`run_tournament_simulation` — runs ``simulate_group_stage`` against
  a list of fixtures and persists one ``simulation_results`` row (§6.4).
* :func:`fan_out_notification` — looks up the user's ``user_push_settings``,
  routes the payload through :class:`PushDispatcher`, and writes one
  ``push_notifications`` row per delivery attempt (§5.3).

The implementations purposely keep all I/O bounded by ``SessionLocal`` and
inject collaborators (LLM client, dispatcher, fixtures) through arguments
so unit tests can drive them without Celery.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy.orm import Session

from src.config.celery_config import app
from src.content.ai_report import (
    AIReportGenerator,
    LLMClient,
    MatchReportContext,
)
from src.ml.simulation.monte_carlo import (
    DEFAULT_TRIALS,
    GroupFixture,
    simulate_group_stage,
)
from src.models.analysis_report import AnalysisReport
from src.models.push import PushNotification, UserPushSettings
from src.models.simulation_result import SimulationResult
from src.push.base import NotificationKind, NotificationPayload, PushDispatcher
from src.utils.db import SessionLocal

logger = structlog.get_logger(__name__)


@app.task(
    name="phase4.generate_match_report",
    queue="reports",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def generate_match_report(
    self,
    *,
    match_id: int,
    prediction_id: int | None,
    context: dict[str, Any],
    model_used: str,
    llm_client: LLMClient | None = None,
) -> int:
    """Generate (and publish) one Chinese AI report. Returns the new row id."""
    if llm_client is None:
        # Pre-launch builds run without LLM keys configured. The factory
        # returns a StubLLMClient that emits a templated 8-section report,
        # so the rest of the pipeline (persistence + push fan-out) can be
        # exercised end-to-end before keys arrive.
        from src.content.ai_report import build_llm_client_from_settings

        llm_client = build_llm_client_from_settings()
    generator = AIReportGenerator(llm_client)
    ctx = MatchReportContext(**context)
    body = generator.generate(ctx)
    summary = _make_summary(body)
    title = f"{ctx.home_team} vs {ctx.away_team} 赛前分析"
    return _persist_ai_report(
        match_id=match_id,
        prediction_id=prediction_id,
        title=title,
        content_md=body,
        summary=summary,
        model_used=model_used,
    )


def _make_summary(body: str, *, limit: int = 240) -> str:
    """Strip whitespace, take the first ``limit`` chars (≤ 500 by schema)."""
    cleaned = " ".join(body.split())
    return cleaned[:limit]


def _persist_ai_report(
    *,
    match_id: int,
    prediction_id: int | None,
    title: str,
    content_md: str,
    summary: str,
    model_used: str,
) -> int:
    """Upsert the *published* row for ``match_id``; supersedes any prior row."""
    now = datetime.now(UTC)
    with SessionLocal() as session:
        existing = (
            session.query(AnalysisReport)
            .filter(AnalysisReport.match_id == match_id)
            .filter(AnalysisReport.status == "published")
            .one_or_none()
        )
        if existing is not None:
            existing.title = title
            existing.content_md = content_md
            existing.summary = summary
            existing.model_used = model_used
            existing.prediction_id = prediction_id
            existing.generated_at = now
            existing.published_at = now
            session.commit()
            return int(existing.id)
        row = AnalysisReport(
            match_id=match_id,
            prediction_id=prediction_id,
            title=title,
            content_md=content_md,
            summary=summary,
            model_used=model_used,
            status="published",
            generated_at=now,
            published_at=now,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return int(row.id)


@app.task(name="phase4.run_tournament_simulation", queue="default")
def run_tournament_simulation(
    *,
    simulation_version: str,
    model_version: str,
    fixtures: list[dict[str, Any]],
    num_simulations: int = DEFAULT_TRIALS,
    seed: int | None = None,
) -> int:
    """Run a Monte Carlo group simulation; persist + return the row id."""
    parsed = [
        GroupFixture(
            home_team=f["home_team"],
            away_team=f["away_team"],
            score_matrix=f["score_matrix"],
        )
        for f in fixtures
    ]
    standings = simulate_group_stage(parsed, trials=num_simulations, seed=seed)
    results_blob: dict[str, Any] = {
        "trials": num_simulations,
        "by_team": {
            s.team: {
                "qualify_first_prob": s.qualify_first_prob,
                "qualify_second_prob": s.qualify_second_prob,
                "qualify_prob": s.qualify_prob,
                "expected_points": s.expected_points,
                "expected_gd": s.expected_gd,
            }
            for s in standings
        },
    }
    with SessionLocal() as session:
        row = SimulationResult(
            simulation_version=simulation_version,
            model_version=model_version,
            num_simulations=num_simulations,
            results=results_blob,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        logger.info(
            "tournament_simulation_persisted",
            simulation_id=row.id,
            simulation_version=simulation_version,
        )
        return int(row.id)


@app.task(name="phase4.fan_out_notification", queue="default")
def fan_out_notification(
    *,
    user_id: int,
    payload: dict[str, Any],
    dispatcher: PushDispatcher | None = None,
) -> list[dict[str, Any]]:
    """Look up settings for ``user_id`` and dispatch ``payload`` to each channel.

    Logs every attempt to ``push_notifications`` (one row per channel).
    """
    if dispatcher is None:
        raise RuntimeError("dispatcher must be wired by the task caller")
    notif_payload = NotificationPayload(
        kind=NotificationKind(payload["kind"]),
        title=payload["title"],
        body=payload["body"],
        deep_link=payload.get("deep_link"),
        target_id=payload.get("target_id"),
        data=payload.get("data") or {},
    )
    with SessionLocal() as session:
        results = _dispatch_for_user(session, user_id, dispatcher, notif_payload)
        for item in results:
            _log_delivery(session, user_id, notif_payload, item)
        session.commit()
    return [
        {
            "channel": r.channel,
            "success": r.success,
            "error": r.error,
            "skipped_reason": r.skipped_reason,
        }
        for r in results
    ]


def _dispatch_for_user(
    session: Session,
    user_id: int,
    dispatcher: PushDispatcher,
    payload: NotificationPayload,
):
    settings = (
        session.query(UserPushSettings)
        .filter(UserPushSettings.user_id == user_id)
        .one_or_none()
    )
    if settings is None:
        return []
    if not _kind_enabled(settings, payload.kind):
        return []
    recipients = _recipients_from_settings(settings)
    if not recipients:
        return []
    return dispatcher.dispatch(
        user_id=user_id,
        recipients_by_channel=recipients,
        payload=payload,
    )


def _kind_enabled(settings: UserPushSettings, kind: NotificationKind) -> bool:
    """Map a :class:`NotificationKind` to the matching ``enable_*`` flag."""
    return {
        NotificationKind.HIGH_EV: settings.enable_high_ev,
        NotificationKind.REPORT: settings.enable_reports,
        NotificationKind.MATCH_START: settings.enable_match_start,
        NotificationKind.RED_HIT: settings.enable_red_hit,
        NotificationKind.MILESTONE: True,  # marketing — always on
    }.get(kind, False)


def _recipients_from_settings(settings: UserPushSettings) -> dict[str, str]:
    """Pick the channel→recipient map from one ``user_push_settings`` row."""
    out: dict[str, str] = {}
    if settings.wechat_openid:
        out["wechat"] = settings.wechat_openid
    if settings.web_push_subscription:
        out["web_push"] = str(settings.web_push_subscription)
    return out


def _log_delivery(
    session: Session,
    user_id: int,
    payload: NotificationPayload,
    result,
) -> None:
    now = datetime.now(UTC) if result.success else None
    session.add(
        PushNotification(
            user_id=user_id,
            channel=result.channel,
            notification_type=payload.kind.value,
            title=payload.title,
            body=payload.body,
            target_url=payload.deep_link,
            status=("sent" if result.success else "failed"),
            sent_at=now,
            meta={
                "provider_message_id": result.provider_message_id,
                "error": result.error,
                "skipped_reason": result.skipped_reason,
            },
        )
    )

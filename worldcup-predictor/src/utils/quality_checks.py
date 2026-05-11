"""Shared data-completeness checks.

The five Phase-1 checks mirror the spec exactly. Both the Celery
`maintenance.check_data_completeness` task and the `scripts/validate_data.py`
CLI consume these functions, so the logic stays single-sourced.

Each check returns a fully-populated `DataQualityAlertPayload` — caller
decides whether to publish to Kafka, print, or both.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from src.events.schemas import DataQualityAlertPayload
from src.models.data_source_log import DataSourceLog
from src.models.injury import Injury
from src.models.match import Match
from src.models.match_stats import MatchStats
from src.models.odds_snapshot import OddsSnapshot

# Tunables — keep collocated so ops can re-tune in one place.
STATS_GRACE_HOURS: int = 24
ODDS_LOOKAHEAD_DAYS: int = 7
INJURY_FRESHNESS_DAYS: int = 7
XG_COVERAGE_MIN: float = 0.80
FAILURE_RATE_MAX: float = 0.05


def run_all(session: Session, *, now: datetime | None = None) -> list[DataQualityAlertPayload]:
    """Run every check and return the payloads in stable order."""
    when = now or datetime.now(UTC)
    return [
        check_missing_stats(session, when),
        check_odds_coverage(session, when),
        check_injury_freshness(session, when),
        check_xg_coverage(session, when),
        check_failure_rate(session, when),
    ]


def check_missing_stats(session: Session, now: datetime) -> DataQualityAlertPayload:
    cutoff = now - timedelta(hours=STATS_GRACE_HOURS)
    stmt = select(func.count(Match.id)).where(
        Match.status == "finished",
        Match.match_date < cutoff,
        ~select(MatchStats.id).where(MatchStats.match_id == Match.id).exists(),
    )
    missing = int(session.execute(stmt).scalar_one() or 0)
    severity = "critical" if missing > 50 else "warning" if missing > 0 else "info"
    return DataQualityAlertPayload(
        check_name="missing_stats_24h",
        severity=severity,
        message=f"{missing} finished matches >24h old still lack match_stats",
        affected_count=missing,
    )


def check_odds_coverage(session: Session, now: datetime) -> DataQualityAlertPayload:
    horizon = now + timedelta(days=ODDS_LOOKAHEAD_DAYS)
    upcoming_stmt = select(func.count(Match.id)).where(
        Match.status == "scheduled",
        Match.match_date.between(now, horizon),
    )
    upcoming = int(session.execute(upcoming_stmt).scalar_one() or 0)

    covered_stmt = select(func.count(func.distinct(OddsSnapshot.match_id))).where(
        OddsSnapshot.match_id.in_(
            select(Match.id).where(
                Match.status == "scheduled",
                Match.match_date.between(now, horizon),
            )
        )
    )
    covered = int(session.execute(covered_stmt).scalar_one() or 0)

    missing = max(upcoming - covered, 0)
    severity = "warning" if missing > 0 and upcoming > 0 else "info"
    return DataQualityAlertPayload(
        check_name="odds_coverage_7d",
        severity=severity,
        message=f"{missing}/{upcoming} upcoming matches in next {ODDS_LOOKAHEAD_DAYS}d lack odds",
        affected_count=missing,
    )


def check_injury_freshness(session: Session, now: datetime) -> DataQualityAlertPayload:
    cutoff = now - timedelta(days=INJURY_FRESHNESS_DAYS)
    stmt = select(func.count(Injury.id)).where(
        Injury.is_active.is_(True),
        Injury.updated_at < cutoff,
    )
    stale = int(session.execute(stmt).scalar_one() or 0)
    severity = "warning" if stale > 0 else "info"
    return DataQualityAlertPayload(
        check_name="injury_freshness",
        severity=severity,
        message=(
            f"{stale} active injury rows have not been refreshed in "
            f"{INJURY_FRESHNESS_DAYS}d"
        ),
        affected_count=stale,
    )


def check_xg_coverage(session: Session, now: datetime) -> DataQualityAlertPayload:
    finished = int(
        session.execute(
            select(func.count(Match.id)).where(Match.status == "finished")
        ).scalar_one()
        or 0
    )
    with_xg = int(
        session.execute(
            select(func.count(func.distinct(MatchStats.match_id))).where(
                MatchStats.xg.is_not(None)
            )
        ).scalar_one()
        or 0
    )
    coverage = (with_xg / finished) if finished else 1.0
    severity = "warning" if coverage < XG_COVERAGE_MIN else "info"
    metadata: dict[str, Any] = {
        "coverage": coverage,
        "finished": finished,
        "with_xg": with_xg,
    }
    return DataQualityAlertPayload(
        check_name="xg_coverage",
        severity=severity,
        message=f"xG coverage on finished matches: {coverage:.1%}",
        affected_count=max(finished - with_xg, 0),
        metadata=metadata,
    )


def check_failure_rate(session: Session, now: datetime) -> DataQualityAlertPayload:
    window_start = now - timedelta(hours=24)
    total = int(
        session.execute(
            select(func.count(DataSourceLog.id)).where(
                DataSourceLog.started_at >= window_start
            )
        ).scalar_one()
        or 0
    )
    failed = int(
        session.execute(
            select(func.count(DataSourceLog.id)).where(
                and_(
                    DataSourceLog.started_at >= window_start,
                    DataSourceLog.status == "failed",
                )
            )
        ).scalar_one()
        or 0
    )
    rate = (failed / total) if total else 0.0
    severity = "critical" if rate > FAILURE_RATE_MAX else "info"
    return DataQualityAlertPayload(
        check_name="ingest_failure_rate_24h",
        severity=severity,
        message=f"24h failure rate: {rate:.1%} ({failed}/{total})",
        affected_count=failed,
        metadata={"rate": rate, "failed": failed, "total": total},
    )

"""GET /api/v1/matches/{id}/report — Phase 4 AI report endpoint.

Returns the *published* Chinese analysis report for a match. Generation is
owned by the offline ``phase4.generate_match_report`` Celery task, so this
endpoint is purely a cache reader.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.api.dependencies import get_db_session
from src.models.analysis_report import AnalysisReport

router = APIRouter(prefix="/api/v1", tags=["reports"])


@router.get("/matches/{match_id}/report")
def get_match_report(
    match_id: int, session: Session = Depends(get_db_session)
) -> dict:
    """Return the published AI report for ``match_id``; 404 if none."""
    report = (
        session.query(AnalysisReport)
        .filter(AnalysisReport.match_id == match_id)
        .filter(AnalysisReport.status == "published")
        .order_by(AnalysisReport.published_at.desc())
        .first()
    )
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": 40400, "error": "REPORT_NOT_FOUND"},
        )
    return {
        "id": report.id,
        "match_id": report.match_id,
        "prediction_id": report.prediction_id,
        "title": report.title,
        "summary": report.summary,
        "content_md": report.content_md,
        "content_html": report.content_html,
        "model_used": report.model_used,
        "generated_at": report.generated_at.isoformat(),
        "published_at": (
            report.published_at.isoformat() if report.published_at else None
        ),
    }

"""Integration tests for the Phase 5 admin page endpoints."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from src.api.dependencies import get_db_session, get_feature_flags
from src.api.main import app
from src.config.settings import settings
from src.models.analysis_report import AnalysisReport
from src.models.data_source_log import DataSourceLog
from src.models.payment import Payment
from src.models.prediction import Prediction
from src.models.push import PushNotification
from src.models.subscription import Subscription
from src.models.user import User
from src.services.feature_flags import FeatureFlagsService, InMemoryFlagBackend

ADMIN_TOKEN = "test-admin-token-please-change-in-production"


@pytest.fixture()
def client(db_session, monkeypatch):  # type: ignore[no-untyped-def]
    monkeypatch.setattr(settings, "ADMIN_API_TOKEN", ADMIN_TOKEN)
    monkeypatch.setattr(settings, "API_KEY", "")
    flags = FeatureFlagsService(InMemoryFlagBackend(), refresh_seconds=60)

    def _db():
        yield db_session

    app.dependency_overrides[get_db_session] = _db
    app.dependency_overrides[get_feature_flags] = lambda: flags
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _h() -> dict[str, str]:
    return {"X-Admin-Token": ADMIN_TOKEN}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _seed_user(db_session, email: str = "u@example.com") -> User:
    u = User(uuid=uuid4(), email=email, nickname="u", subscription_tier="basic")
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    return u


def _seed_subscription(db_session, user_id: int, status: str = "active") -> Subscription:
    now = _now()
    s = Subscription(
        user_id=user_id,
        tier="basic",
        plan_type="monthly",
        status=status,
        price_cny=2900,
        started_at=now,
        expires_at=now + timedelta(days=30),
    )
    db_session.add(s)
    db_session.commit()
    db_session.refresh(s)
    return s


def _seed_payment(db_session, user_id: int, order_no: str, status: str = "paid") -> Payment:
    p = Payment(
        user_id=user_id,
        order_no=order_no,
        payment_channel="alipay",
        amount_cny=2900,
        status=status,
        paid_at=_now() if status == "paid" else None,
    )
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)
    return p


def _seed_prediction(db_session, match_id: int, *, published_at: datetime | None = None) -> Prediction:
    p = Prediction(
        match_id=match_id,
        model_version="poisson_v1",
        feature_version="v1",
        prob_home_win=Decimal("0.45"),
        prob_draw=Decimal("0.30"),
        prob_away_win=Decimal("0.25"),
        lambda_home=Decimal("1.500"),
        lambda_away=Decimal("1.000"),
        score_matrix=[[0.1] * 10] * 10,
        top_scores=[{"score": "1-0", "prob": 0.12}],
        over_under_probs={"2.5": {"over": 0.5, "under": 0.5}},
        confidence_score=70,
        confidence_level="medium",
        features_snapshot={"foo": 1},
        content_hash="x" * 64,
        published_at=published_at or _now(),
    )
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)
    return p


def _seed_report(db_session, match_id: int, status: str = "draft") -> AnalysisReport:
    r = AnalysisReport(
        match_id=match_id,
        title=f"report {match_id}",
        content_md="md",
        summary="sum",
        model_used="claude",
        status=status,
        generated_at=_now(),
    )
    db_session.add(r)
    db_session.commit()
    db_session.refresh(r)
    return r


def _seed_log(
    db_session,
    source_name: str = "api_football",
    status: str = "success",
    started_at: datetime | None = None,
) -> DataSourceLog:
    log = DataSourceLog(
        source_name=source_name,
        task_type="fixtures",
        status=status,
        records_fetched=10,
        records_inserted=10,
        started_at=started_at or _now(),
        finished_at=_now(),
    )
    db_session.add(log)
    db_session.commit()
    db_session.refresh(log)
    return log


def _seed_push(
    db_session,
    user_id: int,
    status: str = "sent",
    *,
    clicked: bool = False,
) -> PushNotification:
    n = PushNotification(
        user_id=user_id,
        channel="web_push",
        notification_type="report",
        title="hi",
        body="b",
        status=status,
        sent_at=_now() if status == "sent" else None,
        clicked_at=_now() if clicked else None,
    )
    db_session.add(n)
    db_session.commit()
    db_session.refresh(n)
    return n


def test_subscriptions_list_returns_total_and_items(client, db_session):
    u = _seed_user(db_session)
    _seed_subscription(db_session, u.id)
    r = client.get("/api/v1/admin/subscriptions", headers=_h())
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert body["items"][0]["user_email"] == u.email
    assert body["items"][0]["tier"] == "basic"


def test_predictions_list_orders_by_published_desc(client, db_session):
    older = _now() - timedelta(hours=2)
    newer = _now()
    _seed_prediction(db_session, match_id=10, published_at=older)
    _seed_prediction(db_session, match_id=11, published_at=newer)
    r = client.get("/api/v1/admin/predictions", headers=_h())
    assert r.status_code == 200
    items = r.json()["items"]
    assert items[0]["match_id"] == 11
    assert items[1]["match_id"] == 10


def test_reports_list_and_filter(client, db_session):
    _seed_report(db_session, match_id=1, status="draft")
    _seed_report(db_session, match_id=2, status="published")
    r_all = client.get("/api/v1/admin/reports", headers=_h())
    assert r_all.json()["total"] == 2
    r_draft = client.get("/api/v1/admin/reports?status=draft", headers=_h())
    assert r_draft.json()["total"] == 1
    assert r_draft.json()["items"][0]["status"] == "draft"


def test_report_publish_and_reject(client, db_session):
    rep = _seed_report(db_session, match_id=42, status="draft")
    pub = client.post(f"/api/v1/admin/reports/{rep.id}/publish", headers=_h())
    assert pub.status_code == 200
    assert pub.json()["status"] == "published"
    assert pub.json()["published_at"] is not None

    rep2 = _seed_report(db_session, match_id=43, status="draft")
    rej = client.post(f"/api/v1/admin/reports/{rep2.id}/reject", headers=_h())
    assert rej.status_code == 200
    assert rej.json()["status"] == "rejected"


def test_report_publish_404(client):
    r = client.post("/api/v1/admin/reports/999999/publish", headers=_h())
    assert r.status_code == 404


def test_report_reject_404(client):
    r = client.post("/api/v1/admin/reports/999999/reject", headers=_h())
    assert r.status_code == 404


def test_data_sources_list_and_summary(client, db_session):
    _seed_log(db_session, "api_football", "success")
    _seed_log(db_session, "api_football", "failed")
    _seed_log(db_session, "fbref", "success")
    lst = client.get("/api/v1/admin/data-sources", headers=_h())
    assert lst.status_code == 200
    assert lst.json()["total"] == 3
    summary = client.get("/api/v1/admin/data-sources/summary", headers=_h())
    assert summary.status_code == 200
    sources = {s["source_name"]: s for s in summary.json()["sources"]}
    assert "api_football" in sources and "fbref" in sources
    assert sources["api_football"]["success_24h"] == 1
    assert sources["api_football"]["failed_24h"] == 1


def test_push_list_and_summary(client, db_session):
    u = _seed_user(db_session, email="p@example.com")
    _seed_push(db_session, u.id, status="sent")
    _seed_push(db_session, u.id, status="failed")
    _seed_push(db_session, u.id, status="pending")
    _seed_push(db_session, u.id, status="sent", clicked=True)

    lst = client.get("/api/v1/admin/push", headers=_h())
    assert lst.status_code == 200
    assert lst.json()["total"] == 4

    summary = client.get("/api/v1/admin/push/summary", headers=_h()).json()
    assert summary["pending"] == 1
    assert summary["sent_24h"] == 2
    assert summary["failed_24h"] == 1
    assert summary["click_through_24h"] == 1


def test_content_moderation_returns_only_drafts(client, db_session):
    _seed_report(db_session, 1, status="draft")
    _seed_report(db_session, 2, status="published")
    _seed_report(db_session, 3, status="draft")
    r = client.get("/api/v1/admin/content/moderation", headers=_h())
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 2
    assert all(it["status"] == "draft" for it in body["items"])


def test_subscriptions_requires_token(client):
    r = client.get("/api/v1/admin/subscriptions")
    assert r.status_code == 401

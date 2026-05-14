"""Unit tests for :class:`PositionService` (M9.5)."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from src.api.schemas.positions import CreatePositionRequest
from src.models.user import User
from src.services.position_service import PositionService


def _make_user(db_session: Session, *, nickname: str = "alice") -> User:
    user = User(
        uuid=uuid.uuid4(),
        nickname=nickname,
        subscription_tier="basic",
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    return user


def _make_create_req(
    *,
    match_id: int,
    outcome: str = "home",
    market: str = "1x2",
    stake: str = "100",
    odds: str = "2.10",
) -> CreatePositionRequest:
    return CreatePositionRequest(
        match_id=match_id,
        platform="pinnacle",
        market=market,
        outcome=outcome,
        stake=Decimal(stake),
        odds=Decimal(odds),
        placed_at=datetime.now(UTC),
        notes=None,
    )


class TestCreate:
    def test_inserts_with_default_active_status(
        self, db_session: Session, make_match, utc
    ) -> None:
        user = _make_user(db_session)
        match = make_match(utc(2026, 6, 5, 18), status="scheduled")

        pos = PositionService.create(
            db_session, user.id, _make_create_req(match_id=match.id)
        )
        assert pos.id is not None
        assert pos.user_id == user.id
        assert pos.status == "active"
        assert pos.platform == "pinnacle"
        assert pos.stake == Decimal("100")

    def test_unknown_match_returns_404(self, db_session: Session) -> None:
        user = _make_user(db_session)
        with pytest.raises(HTTPException) as exc:
            PositionService.create(
                db_session, user.id, _make_create_req(match_id=999_999)
            )
        assert exc.value.status_code == 404


class TestListForUser:
    def test_scopes_to_caller(
        self, db_session: Session, make_match, utc
    ) -> None:
        user_a = _make_user(db_session, nickname="alice")
        user_b = _make_user(db_session, nickname="bob")
        match = make_match(utc(2026, 6, 5, 18), status="scheduled")

        PositionService.create(db_session, user_a.id, _make_create_req(match_id=match.id))
        PositionService.create(db_session, user_b.id, _make_create_req(match_id=match.id))

        a_rows = PositionService.list_for_user(db_session, user_a.id)
        assert len(a_rows) == 1
        assert a_rows[0].user_id == user_a.id

    def test_status_filter(
        self, db_session: Session, make_match, utc
    ) -> None:
        user = _make_user(db_session)
        match = make_match(utc(2026, 6, 5, 18), status="scheduled")
        active_pos = PositionService.create(
            db_session, user.id, _make_create_req(match_id=match.id)
        )
        PositionService.update_status(db_session, user.id, active_pos.id, "hedged")

        hedged = PositionService.list_for_user(db_session, user.id, "hedged")
        active = PositionService.list_for_user(db_session, user.id, "active")
        assert len(hedged) == 1 and hedged[0].id == active_pos.id
        assert len(active) == 0


class TestGetForUser:
    def test_cross_user_returns_404_not_403(
        self, db_session: Session, make_match, utc
    ) -> None:
        owner = _make_user(db_session, nickname="alice")
        intruder = _make_user(db_session, nickname="mallory")
        match = make_match(utc(2026, 6, 5, 18), status="scheduled")
        pos = PositionService.create(
            db_session, owner.id, _make_create_req(match_id=match.id)
        )

        # Mallory tries to read alice's position — we return 404 to avoid
        # leaking existence.
        with pytest.raises(HTTPException) as exc:
            PositionService.get_for_user(db_session, intruder.id, pos.id)
        assert exc.value.status_code == 404


class TestUpdateStatusAndSoftDelete:
    def test_status_transition(
        self, db_session: Session, make_match, utc
    ) -> None:
        user = _make_user(db_session)
        match = make_match(utc(2026, 6, 5, 18), status="scheduled")
        pos = PositionService.create(
            db_session, user.id, _make_create_req(match_id=match.id)
        )
        updated = PositionService.update_status(db_session, user.id, pos.id, "hedged")
        assert updated.status == "hedged"

    def test_soft_delete_sets_cancelled(
        self, db_session: Session, make_match, utc
    ) -> None:
        user = _make_user(db_session)
        match = make_match(utc(2026, 6, 5, 18), status="scheduled")
        pos = PositionService.create(
            db_session, user.id, _make_create_req(match_id=match.id)
        )
        cancelled = PositionService.soft_delete(db_session, user.id, pos.id)
        assert cancelled.status == "cancelled"


class TestMarkSettled:
    def test_records_pnl_and_status(
        self, db_session: Session, make_match, utc
    ) -> None:
        user = _make_user(db_session)
        match = make_match(utc(2026, 6, 5, 18), status="scheduled")
        pos = PositionService.create(
            db_session, user.id, _make_create_req(match_id=match.id)
        )
        settled = PositionService.mark_settled(db_session, pos.id, Decimal("110.00"))
        assert settled.status == "settled"
        assert settled.settlement_pnl == Decimal("110.00")

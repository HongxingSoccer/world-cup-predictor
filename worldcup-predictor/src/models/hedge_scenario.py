"""hedge_scenarios — M9 Hedging Advisory Module ORM models.

Schema reference: ``docs/M9_hedging_module_design.md`` §3.2–3.5.
Migration: ``migrations/versions/20260512_2000_0006_phase4_m9_hedging.py``.

Four tables map to four ORM classes:
    HedgeScenario      — user-created scenario (1 row per scenario)
    HedgeCalculation   — one row per hedge-outcome calculation snapshot
    HedgeResult        — settlement-time outcome + P/L comparison
    ParlayLeg          — per-leg detail for parlay scenarios

GAP-1 note: ``HedgeCalculation.model_assessment`` exists in the ORM but is
documented as nullable because the advisor returns ``None`` when model
probabilities are unavailable (e.g. before kickoff for a brand-new match).
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    SmallInteger,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:  # pragma: no cover — type-only imports
    from .user_position import UserPosition


class HedgeScenario(Base):
    __tablename__ = "hedge_scenarios"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE", name="fk_hedge_scenarios_user"),
        nullable=False,
    )
    scenario_type: Mapped[str] = mapped_column(String(20), nullable=False)
    match_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("matches.id", ondelete="SET NULL", name="fk_hedge_scenarios_match"),
        nullable=True,
    )
    original_stake: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    original_odds: Mapped[Decimal] = mapped_column(Numeric(8, 3), nullable=False)
    original_outcome: Mapped[str] = mapped_column(String(30), nullable=False)
    original_market: Mapped[str] = mapped_column(String(30), nullable=False)
    hedge_mode: Mapped[str] = mapped_column(String(20), nullable=False)
    hedge_ratio: Mapped[Decimal] = mapped_column(
        Numeric(4, 3), nullable=False, server_default=text("1.000")
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'active'")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # M9.5 link — populated when the scenario was launched from an
    # existing user position (push-notification "calculate hedge" flow).
    # NULL for pure calculator scenarios.
    position_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey(
            "user_positions.id",
            ondelete="SET NULL",
            name="fk_hedge_scenarios_position",
        ),
        nullable=True,
    )

    # Relationships — back_populates mirrors are defined below.
    position: Mapped["UserPosition | None"] = relationship(
        back_populates="triggered_scenarios",
        foreign_keys=[position_id],
    )
    calculations: Mapped[list[HedgeCalculation]] = relationship(
        back_populates="scenario",
        cascade="all, delete-orphan",
        order_by="HedgeCalculation.id",
    )
    result: Mapped[HedgeResult | None] = relationship(
        back_populates="scenario",
        cascade="all, delete-orphan",
        uselist=False,
    )
    legs: Mapped[list[ParlayLeg]] = relationship(
        back_populates="scenario",
        cascade="all, delete-orphan",
        order_by="ParlayLeg.leg_order",
    )

    __table_args__ = (
        CheckConstraint(
            "scenario_type IN ('single','parlay','live')",
            name="ck_hedge_scenarios_type",
        ),
        CheckConstraint(
            "original_outcome IN ('home','draw','away','over','under')",
            name="ck_hedge_scenarios_outcome",
        ),
        CheckConstraint(
            "original_market IN ('1x2','over_under','asian_handicap','btts')",
            name="ck_hedge_scenarios_market",
        ),
        CheckConstraint(
            "hedge_mode IN ('full','partial','risk')",
            name="ck_hedge_scenarios_mode",
        ),
        CheckConstraint(
            "hedge_ratio >= 0 AND hedge_ratio <= 1",
            name="ck_hedge_scenarios_ratio",
        ),
        CheckConstraint(
            "status IN ('active','settled','cancelled')",
            name="ck_hedge_scenarios_status",
        ),
        CheckConstraint("original_odds > 1.0", name="ck_hedge_scenarios_odds"),
        CheckConstraint("original_stake > 0", name="ck_hedge_scenarios_stake"),
        Index("idx_hedge_scenarios_user", "user_id", "status"),
        Index("idx_hedge_scenarios_match", "match_id"),
    )


class HedgeCalculation(Base):
    __tablename__ = "hedge_calculations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    scenario_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "hedge_scenarios.id", ondelete="CASCADE", name="fk_hedge_calc_scenario"
        ),
        nullable=False,
    )
    hedge_outcome: Mapped[str] = mapped_column(String(30), nullable=False)
    hedge_odds: Mapped[Decimal] = mapped_column(Numeric(8, 3), nullable=False)
    hedge_bookmaker: Mapped[str] = mapped_column(String(50), nullable=False)
    hedge_stake: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    profit_if_original_wins: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False
    )
    profit_if_hedge_wins: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False
    )
    max_loss: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    guaranteed_profit: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), nullable=True
    )
    ev_of_hedge: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    model_prob_hedge: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4), nullable=True
    )
    # GAP 1 — persisted advisor verdict so history reads don't re-call advisor.
    model_assessment: Mapped[str | None] = mapped_column(String(50), nullable=True)
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    scenario: Mapped[HedgeScenario] = relationship(back_populates="calculations")

    __table_args__ = (
        UniqueConstraint(
            "scenario_id", "hedge_outcome", name="uq_hedge_calc_scenario_outcome"
        ),
        CheckConstraint("hedge_odds > 1.0", name="ck_hedge_calc_odds"),
        CheckConstraint("hedge_stake >= 0", name="ck_hedge_calc_stake"),
        # idx_hedge_calc_ev is created via raw SQL in the migration
        # (DESC NULLS LAST is awkward to express in Index() before SA 2.0.30).
    )


class HedgeResult(Base):
    __tablename__ = "hedge_results"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    scenario_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "hedge_scenarios.id", ondelete="CASCADE", name="fk_hedge_result_scenario"
        ),
        nullable=False,
        unique=True,
    )
    actual_outcome: Mapped[str] = mapped_column(String(30), nullable=False)
    original_pnl: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    hedge_pnl: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    total_pnl: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    # GAP 5 — counterfactual P/L without hedging; cheap to recompute but
    # persisted to keep the settlement job pure-write.
    would_have_pnl: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    hedge_value_added: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    settled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    scenario: Mapped[HedgeScenario] = relationship(back_populates="result")


class ParlayLeg(Base):
    __tablename__ = "parlay_legs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    scenario_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "hedge_scenarios.id", ondelete="CASCADE", name="fk_parlay_legs_scenario"
        ),
        nullable=False,
    )
    leg_order: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    match_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("matches.id", ondelete="RESTRICT", name="fk_parlay_legs_match"),
        nullable=False,
    )
    outcome: Mapped[str] = mapped_column(String(30), nullable=False)
    odds: Mapped[Decimal] = mapped_column(Numeric(8, 3), nullable=False)
    is_settled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    is_won: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    scenario: Mapped[HedgeScenario] = relationship(back_populates="legs")

    __table_args__ = (
        UniqueConstraint("scenario_id", "leg_order", name="uq_parlay_legs_order"),
        CheckConstraint("leg_order > 0", name="ck_parlay_legs_order"),
        CheckConstraint("odds > 1.0", name="ck_parlay_legs_odds"),
        Index("idx_parlay_legs_scenario", "scenario_id", "leg_order"),
        Index("idx_parlay_legs_match", "match_id"),
    )

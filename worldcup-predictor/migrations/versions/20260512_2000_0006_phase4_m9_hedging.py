"""phase4_m9_hedging — M9 Hedging Advisory Module tables.

Revision ID: 0006_phase4_m9_hedging
Revises: 0005_phase5_perf_indexes
Create Date: 2026-05-12 20:00:00

Schema source: ``docs/M9_hedging_module_design.md`` §3.2–3.5.

Creates 4 tables for the M9 hedging-advisory module:

  hedge_scenarios    — user-created scenarios (single / parlay / live)
  hedge_calculations — per-outcome calculation snapshots
  hedge_results     — post-match settlement comparison
  parlay_legs       — per-leg detail for parlay scenarios

Design GAP decisions (M9 design doc has 5 ambiguities; resolved per
prompt header):

  GAP 1: §4.1 API responds with `model_assessment` but §3.3 omits the column.
         DECISION: persist `model_assessment VARCHAR(50)` on hedge_calculations
         so history-read paths avoid re-invoking HedgeAdvisor.

  GAP 2: §3.2 uses enums for outcome/market/mode/status.
         DECISION: implement via CHECK constraints, not PG ENUM. ENUM types
         are painful to migrate (ALTER TYPE … ADD VALUE is the only path,
         no removes); CHECK constraints are dropping/replacing safely.

  GAP 3: §5.3 lists exactly 4 recommendation strings ("建议对冲" /
         "对冲有价值" / "谨慎对冲" / "不建议对冲"). DECISION: do NOT enforce
         at DB level — the advisor may return NULL when probs are unavailable.
         Validation lives in Pydantic / Java DTO layers.

  GAP 4: disclaimer wording. DECISION: §9 paragraph verbatim, single
         source-of-truth constant in src/api/routes/hedge.py.

  GAP 5: hedge_results.would_have_pnl / hedge_value_added. DECISION: compute
         at settlement-time (post-match) and persist; cheap to recompute later
         but storage cost is minimal vs settlement-job complexity.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0006_phase4_m9_hedging"
down_revision: Union[str, None] = "0005_phase5_perf_indexes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -------------------------------------------------------------------------
    # hedge_scenarios
    # -------------------------------------------------------------------------
    op.create_table(
        "hedge_scenarios",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("scenario_type", sa.String(20), nullable=False),
        sa.Column("match_id", sa.BigInteger(), nullable=True),
        sa.Column("original_stake", sa.Numeric(12, 2), nullable=False),
        sa.Column("original_odds", sa.Numeric(8, 3), nullable=False),
        sa.Column("original_outcome", sa.String(30), nullable=False),
        sa.Column("original_market", sa.String(30), nullable=False),
        sa.Column("hedge_mode", sa.String(20), nullable=False),
        sa.Column(
            "hedge_ratio",
            sa.Numeric(4, 3),
            nullable=False,
            server_default=sa.text("1.000"),
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'active'"),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE", name="fk_hedge_scenarios_user"
        ),
        sa.ForeignKeyConstraint(
            ["match_id"],
            ["matches.id"],
            ondelete="SET NULL",
            name="fk_hedge_scenarios_match",
        ),
        sa.CheckConstraint(
            "scenario_type IN ('single','parlay','live')",
            name="ck_hedge_scenarios_type",
        ),
        sa.CheckConstraint(
            "original_outcome IN ('home','draw','away','over','under')",
            name="ck_hedge_scenarios_outcome",
        ),
        sa.CheckConstraint(
            "original_market IN ('1x2','over_under','asian_handicap','btts')",
            name="ck_hedge_scenarios_market",
        ),
        sa.CheckConstraint(
            "hedge_mode IN ('full','partial','risk')",
            name="ck_hedge_scenarios_mode",
        ),
        sa.CheckConstraint(
            "hedge_ratio >= 0 AND hedge_ratio <= 1",
            name="ck_hedge_scenarios_ratio",
        ),
        sa.CheckConstraint(
            "status IN ('active','settled','cancelled')",
            name="ck_hedge_scenarios_status",
        ),
        sa.CheckConstraint(
            "original_odds > 1.0", name="ck_hedge_scenarios_odds"
        ),
        sa.CheckConstraint(
            "original_stake > 0", name="ck_hedge_scenarios_stake"
        ),
    )
    op.create_index(
        "idx_hedge_scenarios_user",
        "hedge_scenarios",
        ["user_id", "status"],
    )
    op.create_index(
        "idx_hedge_scenarios_match",
        "hedge_scenarios",
        ["match_id"],
    )

    # -------------------------------------------------------------------------
    # hedge_calculations  (GAP 1 — adds model_assessment column)
    # -------------------------------------------------------------------------
    op.create_table(
        "hedge_calculations",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("scenario_id", sa.BigInteger(), nullable=False),
        sa.Column("hedge_outcome", sa.String(30), nullable=False),
        sa.Column("hedge_odds", sa.Numeric(8, 3), nullable=False),
        sa.Column("hedge_bookmaker", sa.String(50), nullable=False),
        sa.Column("hedge_stake", sa.Numeric(12, 2), nullable=False),
        sa.Column("profit_if_original_wins", sa.Numeric(12, 2), nullable=False),
        sa.Column("profit_if_hedge_wins", sa.Numeric(12, 2), nullable=False),
        sa.Column("max_loss", sa.Numeric(12, 2), nullable=False),
        sa.Column("guaranteed_profit", sa.Numeric(12, 2), nullable=True),
        sa.Column("ev_of_hedge", sa.Numeric(8, 4), nullable=True),
        sa.Column("model_prob_hedge", sa.Numeric(5, 4), nullable=True),
        # GAP 1 — advisor verdict persisted to avoid recompute on history reads.
        sa.Column("model_assessment", sa.String(50), nullable=True),
        sa.Column(
            "calculated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(
            ["scenario_id"],
            ["hedge_scenarios.id"],
            ondelete="CASCADE",
            name="fk_hedge_calc_scenario",
        ),
        sa.UniqueConstraint(
            "scenario_id", "hedge_outcome", name="uq_hedge_calc_scenario_outcome"
        ),
        sa.CheckConstraint("hedge_odds > 1.0", name="ck_hedge_calc_odds"),
        sa.CheckConstraint("hedge_stake >= 0", name="ck_hedge_calc_stake"),
    )
    # EV-sorted reads (top-EV recommendations across a user's history)
    op.execute(
        "CREATE INDEX idx_hedge_calc_ev ON hedge_calculations "
        "(ev_of_hedge DESC NULLS LAST)"
    )

    # -------------------------------------------------------------------------
    # hedge_results
    # -------------------------------------------------------------------------
    op.create_table(
        "hedge_results",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("scenario_id", sa.BigInteger(), nullable=False, unique=True),
        sa.Column("actual_outcome", sa.String(30), nullable=False),
        sa.Column("original_pnl", sa.Numeric(12, 2), nullable=False),
        sa.Column("hedge_pnl", sa.Numeric(12, 2), nullable=False),
        sa.Column("total_pnl", sa.Numeric(12, 2), nullable=False),
        sa.Column("would_have_pnl", sa.Numeric(12, 2), nullable=False),
        sa.Column("hedge_value_added", sa.Numeric(12, 2), nullable=False),
        sa.Column(
            "settled_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(
            ["scenario_id"],
            ["hedge_scenarios.id"],
            ondelete="CASCADE",
            name="fk_hedge_result_scenario",
        ),
    )

    # -------------------------------------------------------------------------
    # parlay_legs
    # -------------------------------------------------------------------------
    op.create_table(
        "parlay_legs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("scenario_id", sa.BigInteger(), nullable=False),
        sa.Column("leg_order", sa.SmallInteger(), nullable=False),
        sa.Column("match_id", sa.BigInteger(), nullable=False),
        sa.Column("outcome", sa.String(30), nullable=False),
        sa.Column("odds", sa.Numeric(8, 3), nullable=False),
        sa.Column(
            "is_settled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("is_won", sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(
            ["scenario_id"],
            ["hedge_scenarios.id"],
            ondelete="CASCADE",
            name="fk_parlay_legs_scenario",
        ),
        sa.ForeignKeyConstraint(
            ["match_id"],
            ["matches.id"],
            ondelete="RESTRICT",
            name="fk_parlay_legs_match",
        ),
        sa.UniqueConstraint(
            "scenario_id", "leg_order", name="uq_parlay_legs_order"
        ),
        sa.CheckConstraint("leg_order > 0", name="ck_parlay_legs_order"),
        sa.CheckConstraint("odds > 1.0", name="ck_parlay_legs_odds"),
    )
    op.create_index(
        "idx_parlay_legs_scenario",
        "parlay_legs",
        ["scenario_id", "leg_order"],
    )
    op.create_index(
        "idx_parlay_legs_match",
        "parlay_legs",
        ["match_id"],
    )


def downgrade() -> None:
    # Reverse order — children before parents.
    op.drop_index("idx_parlay_legs_match", table_name="parlay_legs")
    op.drop_index("idx_parlay_legs_scenario", table_name="parlay_legs")
    op.drop_table("parlay_legs")

    op.drop_table("hedge_results")

    op.execute("DROP INDEX IF EXISTS idx_hedge_calc_ev")
    op.drop_table("hedge_calculations")

    op.drop_index("idx_hedge_scenarios_match", table_name="hedge_scenarios")
    op.drop_index("idx_hedge_scenarios_user", table_name="hedge_scenarios")
    op.drop_table("hedge_scenarios")

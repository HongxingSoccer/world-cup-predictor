"""phase4_m9_positions — M9.5 live hedging flow tables.

Revision ID: 0007_phase4_m9_positions
Revises: 0006_phase4_m9_hedging
Create Date: 2026-05-13 09:00:00

Schema source: ``docs/M9_5_live_hedging_flow.md`` §1.

Adds three pieces:

  1. NEW TABLE ``user_positions`` — user-tracked bets on external
     platforms. Distinct from ``hedge_scenarios`` (which models a
     calculator snapshot) — a position is a long-lived user record.

  2. ALTER ``hedge_scenarios`` — add ``position_id`` FK so a hedge
     calculation can be linked to the position that triggered it (via
     push notification or manual "calculate from position" flow).

  3. ALTER ``push_notifications`` — add ``position_id`` + ``match_id`` +
     ``read_at`` columns so the new notification centre on the frontend
     can deep-link back to the relevant entity and mark items read.
     The existing schema's ``notification_type`` column serves as the
     ``kind`` field (new values: ``hedge_window``, ``position_settled``);
     the existing ``meta`` JSONB serves as the spec's ``payload`` field.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0007_phase4_m9_positions"
down_revision: Union[str, None] = "0006_phase4_m9_hedging"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -------------------------------------------------------------------------
    # user_positions — user's external-platform bet tracker
    # -------------------------------------------------------------------------
    op.create_table(
        "user_positions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("match_id", sa.BigInteger(), nullable=False),
        sa.Column("platform", sa.String(50), nullable=False),
        sa.Column("market", sa.String(30), nullable=False),
        sa.Column("outcome", sa.String(30), nullable=False),
        sa.Column("stake", sa.Numeric(12, 2), nullable=False),
        sa.Column("odds", sa.Numeric(8, 3), nullable=False),
        sa.Column(
            "placed_at", sa.TIMESTAMP(timezone=True), nullable=False
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'active'"),
        ),
        sa.Column("notes", sa.Text(), nullable=True),
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
        sa.Column(
            "last_alert_at", sa.TIMESTAMP(timezone=True), nullable=True
        ),
        sa.Column(
            "settlement_pnl", sa.Numeric(12, 2), nullable=True
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
            name="fk_user_positions_user",
        ),
        sa.ForeignKeyConstraint(
            ["match_id"],
            ["matches.id"],
            ondelete="RESTRICT",
            name="fk_user_positions_match",
        ),
        sa.CheckConstraint(
            "status IN ('active','hedged','settled','cancelled')",
            name="ck_user_positions_status",
        ),
        sa.CheckConstraint(
            "market IN ('1x2','over_under','asian_handicap','btts')",
            name="ck_user_positions_market",
        ),
        sa.CheckConstraint("stake > 0", name="ck_user_positions_stake"),
        sa.CheckConstraint("odds > 1.0", name="ck_user_positions_odds"),
    )
    op.create_index(
        "idx_positions_user_status",
        "user_positions",
        ["user_id", "status"],
    )
    op.create_index(
        "idx_positions_match", "user_positions", ["match_id"]
    )
    op.execute(
        "CREATE INDEX idx_positions_active_alert "
        "ON user_positions (status, last_alert_at) "
        "WHERE status = 'active'"
    )

    # -------------------------------------------------------------------------
    # hedge_scenarios — add nullable position_id FK
    # -------------------------------------------------------------------------
    op.add_column(
        "hedge_scenarios",
        sa.Column("position_id", sa.BigInteger(), nullable=True),
    )
    op.create_foreign_key(
        "fk_hedge_scenarios_position",
        "hedge_scenarios",
        "user_positions",
        ["position_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "idx_hedge_scenarios_position",
        "hedge_scenarios",
        ["position_id"],
    )

    # -------------------------------------------------------------------------
    # push_notifications — add position_id + match_id + read_at
    #
    # The existing schema (from migration 0004) uses ``notification_type``
    # for the kind field and ``meta`` JSONB for the payload, so those are
    # not re-added. The two foreign-key columns + read_at fill the gap so
    # the notification centre can deep-link and track read state.
    # -------------------------------------------------------------------------
    op.add_column(
        "push_notifications",
        sa.Column("position_id", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "push_notifications",
        sa.Column("match_id", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "push_notifications",
        sa.Column("read_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_push_notifications_position",
        "push_notifications",
        "user_positions",
        ["position_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_push_notifications_match",
        "push_notifications",
        "matches",
        ["match_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.execute(
        "CREATE INDEX idx_notifications_user_unread "
        "ON push_notifications (user_id, read_at)"
    )


def downgrade() -> None:
    # Reverse order: push_notifications additions, then hedge_scenarios, then drop user_positions.
    op.execute("DROP INDEX IF EXISTS idx_notifications_user_unread")
    op.drop_constraint(
        "fk_push_notifications_match", "push_notifications", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_push_notifications_position", "push_notifications", type_="foreignkey"
    )
    op.drop_column("push_notifications", "read_at")
    op.drop_column("push_notifications", "match_id")
    op.drop_column("push_notifications", "position_id")

    op.drop_index(
        "idx_hedge_scenarios_position", table_name="hedge_scenarios"
    )
    op.drop_constraint(
        "fk_hedge_scenarios_position", "hedge_scenarios", type_="foreignkey"
    )
    op.drop_column("hedge_scenarios", "position_id")

    op.execute("DROP INDEX IF EXISTS idx_positions_active_alert")
    op.drop_index("idx_positions_match", table_name="user_positions")
    op.drop_index("idx_positions_user_status", table_name="user_positions")
    op.drop_table("user_positions")

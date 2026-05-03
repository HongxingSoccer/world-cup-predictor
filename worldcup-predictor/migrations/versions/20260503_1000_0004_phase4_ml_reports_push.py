"""phase4_ml_reports_push — Phase 4 schema (analysis_reports, simulation_results,
push_notifications, user_push_settings).

Revision ID: 0004_phase4_ml_reports_push
Revises: 0003_phase3_business_tables
Create Date: 2026-05-03 10:00:00

Schema source: ``docs/design/06_Phase4_ModelEvolution.md`` §4.5, §5.3, §6.4.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0004_phase4_ml_reports_push"
down_revision: Union[str, None] = "0003_phase3_business_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ----- analysis_reports -------------------------------------------------
    op.create_table(
        "analysis_reports",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("match_id", sa.BigInteger(), nullable=False),
        sa.Column("prediction_id", sa.BigInteger(), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("content_md", sa.Text(), nullable=False),
        sa.Column("content_html", sa.Text(), nullable=True),
        sa.Column("summary", sa.String(length=500), nullable=False),
        sa.Column("model_used", sa.String(length=30), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="draft", nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_reports_match_published",
        "analysis_reports",
        ["match_id"],
        unique=True,
        postgresql_where=sa.text("status = 'published'"),
    )
    op.create_index(
        "idx_reports_published", "analysis_reports", ["published_at"], unique=False
    )

    # ----- simulation_results ----------------------------------------------
    op.create_table(
        "simulation_results",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("simulation_version", sa.String(length=30), nullable=False),
        sa.Column(
            "num_simulations", sa.Integer(), server_default="10000", nullable=False
        ),
        sa.Column("model_version", sa.String(length=30), nullable=False),
        sa.Column("results", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_simulation_latest", "simulation_results", ["computed_at"], unique=False
    )

    # ----- push_notifications ----------------------------------------------
    op.create_table(
        "push_notifications",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("channel", sa.String(length=20), nullable=False),
        sa.Column("notification_type", sa.String(length=30), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("target_url", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("clicked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("meta", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_push_user", "push_notifications", ["user_id", "created_at"], unique=False
    )
    op.create_index("idx_push_status", "push_notifications", ["status"], unique=False)

    # ----- user_push_settings ----------------------------------------------
    op.create_table(
        "user_push_settings",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("wechat_openid", sa.String(length=100), nullable=True),
        sa.Column(
            "web_push_subscription",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "enable_high_ev", sa.Boolean(), server_default="true", nullable=False
        ),
        sa.Column(
            "enable_reports", sa.Boolean(), server_default="true", nullable=False
        ),
        sa.Column(
            "enable_match_start", sa.Boolean(), server_default="true", nullable=False
        ),
        sa.Column(
            "enable_red_hit", sa.Boolean(), server_default="true", nullable=False
        ),
        sa.Column("quiet_hours_start", sa.Time(), nullable=True),
        sa.Column("quiet_hours_end", sa.Time(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_user_push_settings_user"),
    )


def downgrade() -> None:
    op.drop_table("user_push_settings")
    op.drop_index("idx_push_status", table_name="push_notifications")
    op.drop_index("idx_push_user", table_name="push_notifications")
    op.drop_table("push_notifications")
    op.drop_index("idx_simulation_latest", table_name="simulation_results")
    op.drop_table("simulation_results")
    op.drop_index("idx_reports_published", table_name="analysis_reports")
    op.drop_index("uq_reports_match_published", table_name="analysis_reports")
    op.drop_table("analysis_reports")

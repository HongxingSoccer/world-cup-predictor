"""phase2_ml_tables — feature store, predictions, odds analysis (3 tables).

Revision ID: 0002_phase2_ml_tables
Revises: 0001_initial_schema
Create Date: 2026-05-02 17:59:21

Adds the Phase-2 schema:

    - match_features  : versioned JSONB feature store + nullable label columns.
    - predictions     : append-only model output, protected by an
                        immutability trigger (UPDATE / DELETE rejected
                        at the database level).
    - odds_analysis   : per-outcome value signals computed from a Prediction
                        + the latest OddsSnapshot.

Generated via ``alembic revision --autogenerate``; the trigger SQL was added
manually after generation.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0002_phase2_ml_tables"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Trigger function rejects UPDATE / DELETE on `predictions` at the DB level.
# We deploy as a plain function + trigger pair so the same logic can be
# attached to additional tables later (e.g. published_reports).
_CREATE_IMMUTABLE_TRIGGER_SQL = """
CREATE OR REPLACE FUNCTION reject_predictions_modification()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION
        'predictions are immutable: UPDATE/DELETE is forbidden (op=%)',
        TG_OP
        USING ERRCODE = 'check_violation';
END;
$$;

CREATE TRIGGER predictions_immutable
BEFORE UPDATE OR DELETE ON predictions
FOR EACH ROW EXECUTE FUNCTION reject_predictions_modification();
"""

_DROP_IMMUTABLE_TRIGGER_SQL = """
DROP TRIGGER IF EXISTS predictions_immutable ON predictions;
DROP FUNCTION IF EXISTS reject_predictions_modification();
"""


def upgrade() -> None:
    # --- match_features ---
    op.create_table(
        "match_features",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("match_id", sa.BigInteger(), nullable=False),
        sa.Column("feature_version", sa.String(length=10), nullable=False),
        sa.Column("features", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("label_home_score", sa.SmallInteger(), nullable=True),
        sa.Column("label_away_score", sa.SmallInteger(), nullable=True),
        sa.Column("label_result", sa.String(length=5), nullable=True),
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
        sa.ForeignKeyConstraint(["match_id"], ["matches.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "match_id", "feature_version", name="uq_match_features_match_version"
        ),
    )

    # --- predictions ---
    op.create_table(
        "predictions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("match_id", sa.BigInteger(), nullable=False),
        sa.Column("model_version", sa.String(length=30), nullable=False),
        sa.Column("feature_version", sa.String(length=10), nullable=False),
        sa.Column("prob_home_win", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("prob_draw", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("prob_away_win", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("lambda_home", sa.Numeric(precision=5, scale=3), nullable=False),
        sa.Column("lambda_away", sa.Numeric(precision=5, scale=3), nullable=False),
        sa.Column("score_matrix", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("top_scores", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "over_under_probs",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("btts_prob", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column("confidence_score", sa.SmallInteger(), nullable=False),
        sa.Column("confidence_level", sa.String(length=10), nullable=False),
        sa.Column(
            "features_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["match_id"], ["matches.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "match_id", "model_version", name="uq_predictions_match_model"
        ),
    )
    op.create_index(
        "idx_predictions_confidence",
        "predictions",
        [sa.literal_column("confidence_score DESC")],
    )
    op.create_index(
        "idx_predictions_published",
        "predictions",
        [sa.literal_column("published_at DESC")],
    )

    # Database-level immutability for predictions.
    op.execute(_CREATE_IMMUTABLE_TRIGGER_SQL)

    # --- odds_analysis ---
    op.create_table(
        "odds_analysis",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("match_id", sa.BigInteger(), nullable=False),
        sa.Column("prediction_id", sa.BigInteger(), nullable=False),
        sa.Column("market_type", sa.String(length=30), nullable=False),
        sa.Column("market_value", sa.String(length=20), nullable=True),
        sa.Column("outcome", sa.String(length=20), nullable=False),
        sa.Column("model_prob", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("best_odds", sa.Numeric(precision=6, scale=3), nullable=False),
        sa.Column("best_bookmaker", sa.String(length=50), nullable=False),
        sa.Column("implied_prob", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("ev", sa.Numeric(precision=6, scale=4), nullable=False),
        sa.Column("edge", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column(
            "signal_level",
            sa.SmallInteger(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "analyzed_at",
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
        sa.ForeignKeyConstraint(["match_id"], ["matches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["prediction_id"], ["predictions.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_odds_analysis_market", "odds_analysis", ["market_type"])
    op.create_index("idx_odds_analysis_match", "odds_analysis", ["match_id"])
    op.create_index(
        "idx_odds_analysis_signal",
        "odds_analysis",
        [
            sa.literal_column("signal_level DESC"),
            sa.literal_column("analyzed_at DESC"),
        ],
    )


def downgrade() -> None:
    op.drop_index("idx_odds_analysis_signal", table_name="odds_analysis")
    op.drop_index("idx_odds_analysis_match", table_name="odds_analysis")
    op.drop_index("idx_odds_analysis_market", table_name="odds_analysis")
    op.drop_table("odds_analysis")

    op.execute(_DROP_IMMUTABLE_TRIGGER_SQL)
    op.drop_index("idx_predictions_published", table_name="predictions")
    op.drop_index("idx_predictions_confidence", table_name="predictions")
    op.drop_table("predictions")

    op.drop_table("match_features")

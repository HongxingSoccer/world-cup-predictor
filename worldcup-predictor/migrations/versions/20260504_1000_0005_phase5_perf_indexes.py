"""phase5_perf_indexes — Phase 5 hot-path composite indexes.

Revision ID: 0005_phase5_perf_indexes
Revises: 0004_phase4_ml_reports_push
Create Date: 2026-05-04 10:00:00

Schema source: ``docs/design/07_Phase5_Productization.md`` §5.2.

Adds composite indexes to accelerate the highest-volume read paths:

* predictions(match_id, published_at desc) — "latest prediction for a match"
* matches(status, match_date) — homepage "today / live / upcoming" feeds
* odds_snapshots(bookmaker, snapshot_at desc) — bookmaker-line trend charts
* analysis_reports(match_id, status) — admin moderation queue
* push_notifications(user_id, status, created_at desc) — user inbox

Partitioning hint (NOT executed): in production, ``odds_snapshots`` should be
range-partitioned by month (RANGE on snapshot_at) once volume crosses ~50M
rows; that needs an offline migration window so it's intentionally deferred.
"""
from typing import Sequence, Union

from alembic import op


revision: str = "0005_phase5_perf_indexes"
down_revision: Union[str, None] = "0004_phase4_ml_reports_push"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "idx_predictions_match_published",
        "predictions",
        ["match_id", "published_at"],
        unique=False,
    )
    op.create_index(
        "idx_matches_status_date",
        "matches",
        ["status", "match_date"],
        unique=False,
    )
    op.create_index(
        "idx_odds_bookmaker_time",
        "odds_snapshots",
        ["bookmaker", "snapshot_at"],
        unique=False,
    )
    op.create_index(
        "idx_analysis_reports_match_status",
        "analysis_reports",
        ["match_id", "status"],
        unique=False,
    )
    op.create_index(
        "idx_push_user_status_created",
        "push_notifications",
        ["user_id", "status", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_push_user_status_created", table_name="push_notifications")
    op.drop_index("idx_analysis_reports_match_status", table_name="analysis_reports")
    op.drop_index("idx_odds_bookmaker_time", table_name="odds_snapshots")
    op.drop_index("idx_matches_status_date", table_name="matches")
    op.drop_index("idx_predictions_match_published", table_name="predictions")

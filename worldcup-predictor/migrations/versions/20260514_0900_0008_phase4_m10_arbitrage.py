"""phase4_m10_arbitrage — M10 cross-platform arbitrage tables.

Revision ID: 0008_phase4_m10_arbitrage
Revises: 0007_phase4_m9_positions
Create Date: 2026-05-14 09:00:00

Schema source: ``docs/M10_arbitrage_scanner_design.md`` §1.

Two new tables:

  1. ``arb_opportunities`` — append-only record of every arbitrage the
     scanner finds. Status flips to 'expired' once the underlying
     bookmaker odds move enough to break the arb, or the kick-off
     passes. We never UPDATE the JSON math — a re-detection produces a
     fresh row.

  2. ``user_arb_watchlist`` — user opts into a specific filter (min
     profit margin, optional competition / market subset). The scanner
     worker uses these rules to decide who gets a push for each newly
     found opportunity.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0008_phase4_m10_arbitrage"
down_revision: Union[str, None] = "0007_phase4_m9_positions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -------------------------------------------------------------------------
    # arb_opportunities — book-of-record for every detected arbitrage
    # -------------------------------------------------------------------------
    op.create_table(
        "arb_opportunities",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "match_id",
            sa.BigInteger,
            sa.ForeignKey("matches.id", ondelete="CASCADE",
                          name="fk_arb_opp_match"),
            nullable=False,
        ),
        sa.Column("market_type", sa.String(30), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
        # arb_total = sum(1/best_odds_i). < 1.0 == arbitrage exists.
        sa.Column("arb_total", sa.Numeric(8, 6), nullable=False),
        # profit_margin = (1 - arb_total) / arb_total, expressed as a fraction
        # (0.025 = 2.5% guaranteed return on bankroll).
        sa.Column("profit_margin", sa.Numeric(8, 6), nullable=False),
        # best_odds is a JSON map outcome → {odds, bookmaker, captured_at}.
        sa.Column("best_odds", postgresql.JSONB, nullable=False),
        # stake_distribution is a JSON map outcome → fraction-of-bankroll.
        # Sum is always 1.0. Multiply by user's bankroll to get per-leg stake.
        sa.Column("stake_distribution", postgresql.JSONB, nullable=False),
        sa.Column("status", sa.String(20), nullable=False,
                  server_default="active"),
        sa.Column("expired_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('active','expired','stale')",
            name="ck_arb_opportunities_status",
        ),
        sa.CheckConstraint(
            "arb_total > 0", name="ck_arb_opportunities_total"
        ),
        sa.CheckConstraint(
            "profit_margin >= 0", name="ck_arb_opportunities_margin"
        ),
    )
    op.create_index(
        "idx_arb_opp_match_market", "arb_opportunities",
        ["match_id", "market_type", "status"],
    )
    op.create_index(
        "idx_arb_opp_detected_at", "arb_opportunities", ["detected_at"],
    )
    # Partial index on active rows — the scanner reads this constantly.
    op.execute(
        "CREATE INDEX idx_arb_opp_active_margin ON arb_opportunities "
        "(profit_margin DESC, detected_at DESC) WHERE status = 'active'"
    )

    # -------------------------------------------------------------------------
    # user_arb_watchlist — per-user notification filter rules
    # -------------------------------------------------------------------------
    op.create_table(
        "user_arb_watchlist",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.BigInteger,
            sa.ForeignKey("users.id", ondelete="CASCADE",
                          name="fk_arb_watchlist_user"),
            nullable=False,
        ),
        # Optional scope filters — NULL means "any".
        sa.Column(
            "competition_id",
            sa.BigInteger,
            sa.ForeignKey("competitions.id", ondelete="SET NULL",
                          name="fk_arb_watchlist_competition"),
            nullable=True,
        ),
        # Markets the user cares about. NULL = all. Stored as JSON array,
        # not a Postgres text[] — keeps SQLite-portability for tests.
        sa.Column("market_types", postgresql.JSONB, nullable=True),
        # Minimum profit-margin (e.g. 0.02 = "only push 2%+ arbitrage").
        sa.Column("min_profit_margin", sa.Numeric(8, 6),
                  nullable=False, server_default="0.01"),
        sa.Column("notify_enabled", sa.Boolean,
                  nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "min_profit_margin >= 0",
            name="ck_user_arb_watchlist_min_margin",
        ),
    )
    op.create_index(
        "idx_arb_watchlist_user_enabled", "user_arb_watchlist",
        ["user_id", "notify_enabled"],
    )


def downgrade() -> None:
    op.drop_index("idx_arb_watchlist_user_enabled", table_name="user_arb_watchlist")
    op.drop_table("user_arb_watchlist")

    op.execute("DROP INDEX IF EXISTS idx_arb_opp_active_margin")
    op.drop_index("idx_arb_opp_detected_at", table_name="arb_opportunities")
    op.drop_index("idx_arb_opp_match_market", table_name="arb_opportunities")
    op.drop_table("arb_opportunities")

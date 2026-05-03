"""initial schema — Phase 1 data foundation (15 tables)

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-05-01 00:00:00

Creates the full Phase-1 data-foundation schema:
competitions, seasons, teams, players, matches, match_stats, match_lineups,
player_stats, player_valuations, injuries, odds_snapshots, h2h_records,
elo_ratings, data_source_logs, team_name_aliases.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---------- competitions ----------
    op.create_table(
        "competitions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("api_football_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("name_zh", sa.String(length=200), nullable=True),
        sa.Column("competition_type", sa.String(length=20), nullable=False),
        sa.Column("country", sa.String(length=100), nullable=True),
        sa.Column("logo_url", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("api_football_id", name="uq_competitions_api_football_id"),
    )
    op.create_index(
        "idx_competitions_type_country",
        "competitions",
        ["competition_type", "country"],
    )

    # ---------- teams ----------
    op.create_table(
        "teams",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("api_football_id", sa.Integer(), nullable=True),
        sa.Column("transfermarkt_id", sa.String(length=50), nullable=True),
        sa.Column("fbref_id", sa.String(length=50), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("name_zh", sa.String(length=200), nullable=True),
        sa.Column("short_name", sa.String(length=50), nullable=True),
        sa.Column("country", sa.String(length=100), nullable=True),
        sa.Column("team_type", sa.String(length=20), nullable=False),
        sa.Column("logo_url", sa.Text(), nullable=True),
        sa.Column("fifa_ranking", sa.SmallInteger(), nullable=True),
        sa.Column("fifa_ranking_updated", sa.Date(), nullable=True),
        sa.Column("confederation", sa.String(length=20), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "uq_teams_api_football_id",
        "teams",
        ["api_football_id"],
        unique=True,
        postgresql_where=sa.text("api_football_id IS NOT NULL"),
    )
    op.create_index("idx_teams_name", "teams", ["name"])
    op.create_index("idx_teams_country_type", "teams", ["country", "team_type"])

    # ---------- seasons ----------
    op.create_table(
        "seasons",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "competition_id",
            sa.BigInteger(),
            sa.ForeignKey("competitions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("year", sa.SmallInteger(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("competition_id", "year", name="uq_seasons_competition_year"),
    )

    # ---------- players ----------
    op.create_table(
        "players",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("api_football_id", sa.Integer(), nullable=True),
        sa.Column("transfermarkt_id", sa.String(length=50), nullable=True),
        sa.Column("fbref_id", sa.String(length=50), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("name_zh", sa.String(length=200), nullable=True),
        sa.Column("nationality", sa.String(length=100), nullable=True),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column("position", sa.String(length=30), nullable=True),
        sa.Column(
            "current_team_id",
            sa.BigInteger(),
            sa.ForeignKey("teams.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "national_team_id",
            sa.BigInteger(),
            sa.ForeignKey("teams.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("market_value_eur", sa.BigInteger(), nullable=True),
        sa.Column("market_value_updated", sa.Date(), nullable=True),
        sa.Column("photo_url", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "uq_players_api_football_id",
        "players",
        ["api_football_id"],
        unique=True,
        postgresql_where=sa.text("api_football_id IS NOT NULL"),
    )
    op.create_index("idx_players_team", "players", ["current_team_id"])
    op.create_index("idx_players_nationality", "players", ["nationality"])

    # ---------- matches ----------
    op.create_table(
        "matches",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("api_football_id", sa.Integer(), nullable=True),
        sa.Column(
            "season_id",
            sa.BigInteger(),
            sa.ForeignKey("seasons.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "home_team_id",
            sa.BigInteger(),
            sa.ForeignKey("teams.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "away_team_id",
            sa.BigInteger(),
            sa.ForeignKey("teams.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("match_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("venue", sa.String(length=200), nullable=True),
        sa.Column("round", sa.String(length=50), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="scheduled"),
        sa.Column("home_score", sa.SmallInteger(), nullable=True),
        sa.Column("away_score", sa.SmallInteger(), nullable=True),
        sa.Column("home_score_ht", sa.SmallInteger(), nullable=True),
        sa.Column("away_score_ht", sa.SmallInteger(), nullable=True),
        sa.Column("referee", sa.String(length=100), nullable=True),
        sa.Column("attendance", sa.Integer(), nullable=True),
        sa.Column("data_completeness", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('scheduled','live','finished','postponed','cancelled')",
            name="ck_matches_status",
        ),
    )
    op.create_index(
        "uq_matches_api_football_id",
        "matches",
        ["api_football_id"],
        unique=True,
        postgresql_where=sa.text("api_football_id IS NOT NULL"),
    )
    op.create_index("idx_matches_date", "matches", [sa.text("match_date DESC")])
    op.create_index("idx_matches_season", "matches", ["season_id"])
    op.create_index("idx_matches_teams", "matches", ["home_team_id", "away_team_id"])
    op.create_index("idx_matches_status", "matches", ["status"])

    # ---------- match_stats ----------
    op.create_table(
        "match_stats",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "match_id",
            sa.BigInteger(),
            sa.ForeignKey("matches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "team_id",
            sa.BigInteger(),
            sa.ForeignKey("teams.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("is_home", sa.Boolean(), nullable=False),
        sa.Column("possession", sa.Numeric(4, 1), nullable=True),
        sa.Column("shots", sa.SmallInteger(), nullable=True),
        sa.Column("shots_on_target", sa.SmallInteger(), nullable=True),
        sa.Column("xg", sa.Numeric(5, 2), nullable=True),
        sa.Column("xg_against", sa.Numeric(5, 2), nullable=True),
        sa.Column("passes", sa.SmallInteger(), nullable=True),
        sa.Column("pass_accuracy", sa.Numeric(4, 1), nullable=True),
        sa.Column("corners", sa.SmallInteger(), nullable=True),
        sa.Column("fouls", sa.SmallInteger(), nullable=True),
        sa.Column("yellow_cards", sa.SmallInteger(), nullable=True),
        sa.Column("red_cards", sa.SmallInteger(), nullable=True),
        sa.Column("offsides", sa.SmallInteger(), nullable=True),
        sa.Column("tackles", sa.SmallInteger(), nullable=True),
        sa.Column("interceptions", sa.SmallInteger(), nullable=True),
        sa.Column("saves", sa.SmallInteger(), nullable=True),
        sa.Column("data_source", sa.String(length=30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("match_id", "team_id", name="uq_match_stats_match_team"),
    )
    op.create_index("idx_match_stats_team", "match_stats", ["team_id", "match_id"])

    # ---------- match_lineups ----------
    op.create_table(
        "match_lineups",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "match_id",
            sa.BigInteger(),
            sa.ForeignKey("matches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "team_id",
            sa.BigInteger(),
            sa.ForeignKey("teams.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "player_id",
            sa.BigInteger(),
            sa.ForeignKey("players.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("is_starter", sa.Boolean(), nullable=False),
        sa.Column("position", sa.String(length=30), nullable=True),
        sa.Column("jersey_number", sa.SmallInteger(), nullable=True),
        sa.Column("minutes_played", sa.SmallInteger(), nullable=True),
        sa.Column("sub_in_minute", sa.SmallInteger(), nullable=True),
        sa.Column("sub_out_minute", sa.SmallInteger(), nullable=True),
        sa.Column("rating", sa.Numeric(3, 1), nullable=True),
        sa.UniqueConstraint("match_id", "team_id", "player_id", name="uq_lineups_match_team_player"),
    )
    op.create_index("idx_lineups_player", "match_lineups", ["player_id"])

    # ---------- player_stats ----------
    op.create_table(
        "player_stats",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "match_id",
            sa.BigInteger(),
            sa.ForeignKey("matches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "player_id",
            sa.BigInteger(),
            sa.ForeignKey("players.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "team_id",
            sa.BigInteger(),
            sa.ForeignKey("teams.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("goals", sa.SmallInteger(), server_default="0"),
        sa.Column("assists", sa.SmallInteger(), server_default="0"),
        sa.Column("xg", sa.Numeric(4, 2), nullable=True),
        sa.Column("xa", sa.Numeric(4, 2), nullable=True),
        sa.Column("shots", sa.SmallInteger(), nullable=True),
        sa.Column("key_passes", sa.SmallInteger(), nullable=True),
        sa.Column("tackles", sa.SmallInteger(), nullable=True),
        sa.Column("interceptions", sa.SmallInteger(), nullable=True),
        sa.Column("saves", sa.SmallInteger(), nullable=True),
        sa.Column("yellow_cards", sa.SmallInteger(), server_default="0"),
        sa.Column("red_cards", sa.SmallInteger(), server_default="0"),
        sa.Column("data_source", sa.String(length=30), nullable=False),
        sa.UniqueConstraint("match_id", "player_id", name="uq_player_stats_match_player"),
    )
    op.create_index("idx_player_stats_player", "player_stats", ["player_id"])
    op.create_index("idx_player_stats_team_match", "player_stats", ["team_id", "match_id"])

    # ---------- player_valuations ----------
    op.create_table(
        "player_valuations",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "player_id",
            sa.BigInteger(),
            sa.ForeignKey("players.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "team_id",
            sa.BigInteger(),
            sa.ForeignKey("teams.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("value_date", sa.Date(), nullable=False),
        sa.Column("market_value_eur", sa.BigInteger(), nullable=False),
        sa.Column("data_source", sa.String(length=30), nullable=False, server_default="transfermarkt"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("player_id", "value_date", name="uq_valuations_player_date"),
    )
    op.create_index("idx_valuations_date", "player_valuations", [sa.text("value_date DESC")])

    # ---------- injuries ----------
    op.create_table(
        "injuries",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "player_id",
            sa.BigInteger(),
            sa.ForeignKey("players.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "team_id",
            sa.BigInteger(),
            sa.ForeignKey("teams.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("injury_type", sa.String(length=100), nullable=True),
        sa.Column("severity", sa.String(length=20), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("expected_return", sa.Date(), nullable=True),
        sa.Column("actual_return", sa.Date(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("data_source", sa.String(length=30), nullable=False, server_default="transfermarkt"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_injuries_player_active", "injuries", ["player_id", "is_active"])
    op.create_index("idx_injuries_team_active", "injuries", ["team_id", "is_active"])

    # ---------- odds_snapshots ----------
    op.create_table(
        "odds_snapshots",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "match_id",
            sa.BigInteger(),
            sa.ForeignKey("matches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("bookmaker", sa.String(length=50), nullable=False),
        sa.Column("market_type", sa.String(length=30), nullable=False),
        sa.Column("market_value", sa.String(length=20), nullable=True),
        sa.Column("outcome_home", sa.Numeric(6, 3), nullable=True),
        sa.Column("outcome_draw", sa.Numeric(6, 3), nullable=True),
        sa.Column("outcome_away", sa.Numeric(6, 3), nullable=True),
        sa.Column("outcome_over", sa.Numeric(6, 3), nullable=True),
        sa.Column("outcome_under", sa.Numeric(6, 3), nullable=True),
        sa.Column("outcome_yes", sa.Numeric(6, 3), nullable=True),
        sa.Column("outcome_no", sa.Numeric(6, 3), nullable=True),
        sa.Column("snapshot_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("data_source", sa.String(length=30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "idx_odds_match_market",
        "odds_snapshots",
        ["match_id", "market_type", sa.text("snapshot_at DESC")],
    )
    op.create_index(
        "idx_odds_snapshot_time",
        "odds_snapshots",
        [sa.text("snapshot_at DESC")],
    )

    # ---------- h2h_records ----------
    op.create_table(
        "h2h_records",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "team_a_id",
            sa.BigInteger(),
            sa.ForeignKey("teams.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "team_b_id",
            sa.BigInteger(),
            sa.ForeignKey("teams.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("total_matches", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("team_a_wins", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("team_b_wins", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("draws", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("team_a_goals", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("team_b_goals", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("last_match_date", sa.Date(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("team_a_id", "team_b_id", name="uq_h2h_pair"),
        sa.CheckConstraint("team_a_id < team_b_id", name="ck_h2h_canonical_order"),
    )

    # ---------- elo_ratings ----------
    op.create_table(
        "elo_ratings",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "team_id",
            sa.BigInteger(),
            sa.ForeignKey("teams.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "match_id",
            sa.BigInteger(),
            sa.ForeignKey("matches.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("rating", sa.Numeric(7, 2), nullable=False, server_default="1500.00"),
        sa.Column("rating_change", sa.Numeric(6, 2), nullable=True),
        sa.Column("rated_at", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_elo_team_date", "elo_ratings", ["team_id", sa.text("rated_at DESC")])
    op.create_index("idx_elo_match", "elo_ratings", ["match_id"])

    # ---------- data_source_logs ----------
    op.create_table(
        "data_source_logs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("source_name", sa.String(length=50), nullable=False),
        sa.Column("task_type", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("records_fetched", sa.Integer(), nullable=True),
        sa.Column("records_inserted", sa.Integer(), nullable=True),
        sa.Column("records_updated", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("meta", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "idx_logs_source_time",
        "data_source_logs",
        ["source_name", sa.text("started_at DESC")],
    )
    op.create_index("idx_logs_status", "data_source_logs", ["status"])

    # ---------- team_name_aliases ----------
    op.create_table(
        "team_name_aliases",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "team_id",
            sa.BigInteger(),
            sa.ForeignKey("teams.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("alias", sa.String(length=200), nullable=False),
        sa.Column("source", sa.String(length=30), nullable=False),
        sa.UniqueConstraint("alias", "source", name="uq_team_alias_source"),
    )


def downgrade() -> None:
    # Reverse-dependency order.
    op.drop_table("team_name_aliases")

    op.drop_index("idx_logs_status", table_name="data_source_logs")
    op.drop_index("idx_logs_source_time", table_name="data_source_logs")
    op.drop_table("data_source_logs")

    op.drop_index("idx_elo_match", table_name="elo_ratings")
    op.drop_index("idx_elo_team_date", table_name="elo_ratings")
    op.drop_table("elo_ratings")

    op.drop_table("h2h_records")

    op.drop_index("idx_odds_snapshot_time", table_name="odds_snapshots")
    op.drop_index("idx_odds_match_market", table_name="odds_snapshots")
    op.drop_table("odds_snapshots")

    op.drop_index("idx_injuries_team_active", table_name="injuries")
    op.drop_index("idx_injuries_player_active", table_name="injuries")
    op.drop_table("injuries")

    op.drop_index("idx_valuations_date", table_name="player_valuations")
    op.drop_table("player_valuations")

    op.drop_index("idx_player_stats_team_match", table_name="player_stats")
    op.drop_index("idx_player_stats_player", table_name="player_stats")
    op.drop_table("player_stats")

    op.drop_index("idx_lineups_player", table_name="match_lineups")
    op.drop_table("match_lineups")

    op.drop_index("idx_match_stats_team", table_name="match_stats")
    op.drop_table("match_stats")

    op.drop_index("idx_matches_status", table_name="matches")
    op.drop_index("idx_matches_teams", table_name="matches")
    op.drop_index("idx_matches_season", table_name="matches")
    op.drop_index("idx_matches_date", table_name="matches")
    op.drop_index("uq_matches_api_football_id", table_name="matches")
    op.drop_table("matches")

    op.drop_index("idx_players_nationality", table_name="players")
    op.drop_index("idx_players_team", table_name="players")
    op.drop_index("uq_players_api_football_id", table_name="players")
    op.drop_table("players")

    op.drop_table("seasons")

    op.drop_index("idx_teams_country_type", table_name="teams")
    op.drop_index("idx_teams_name", table_name="teams")
    op.drop_index("uq_teams_api_football_id", table_name="teams")
    op.drop_table("teams")

    op.drop_index("idx_competitions_type_country", table_name="competitions")
    op.drop_table("competitions")

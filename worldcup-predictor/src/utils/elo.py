"""Elo rating math + historical backfill helper.

Elo is the single most important non-ML feature in the system: every prediction
model uses the home/away ratings as inputs. Numbers below match the project
spec — initial 1500, K=60 for national-team friendlies/qualifiers, K=80 for
World-Cup matches, K=40 for clubs.

The pure-math helpers (`expected_score`, `update_ratings`) have no side
effects and are pleasant to test. `backfill_elo_ratings()` is the orchestrator
that walks the matches table chronologically and persists per-match snapshots
to `elo_ratings`.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import NamedTuple

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models.competition import Competition
from src.models.elo_rating import EloRating
from src.models.match import Match
from src.models.season import Season

logger = structlog.get_logger(__name__)

# Project-spec constants.
INITIAL_RATING: float = 1500.0
K_NATIONAL: float = 60.0
K_WORLD_CUP: float = 80.0
K_CLUB: float = 40.0


@dataclass(frozen=True)
class EloUpdate:
    """One match's effect on both teams' ratings."""

    new_home_rating: float
    new_away_rating: float
    home_change: float
    away_change: float


class _MatchRow(NamedTuple):
    match_id: int
    home_team_id: int
    away_team_id: int
    home_score: int
    away_score: int
    match_date_iso: str  # ISO-8601 used only for logging context
    competition_type: str
    competition_name: str


# --- Pure math ---


def expected_score(rating_a: float, rating_b: float) -> float:
    """Standard Elo expected score for player A vs player B.

    Args:
        rating_a: Subject team's current rating.
        rating_b: Opponent's current rating.

    Returns:
        Probability that A "wins" in the 0/0.5/1 sense, in (0, 1).

    Example:
        >>> round(expected_score(1500, 1500), 3)
        0.5
    """
    return 1.0 / (1.0 + 10.0 ** (-(rating_a - rating_b) / 400.0))


def update_ratings(
    *,
    home_rating: float,
    away_rating: float,
    home_score: int,
    away_score: int,
    k_factor: float,
) -> EloUpdate:
    """Apply one match result to both ratings.

    Args:
        home_rating: Pre-match home Elo.
        away_rating: Pre-match away Elo.
        home_score: Final home goals.
        away_score: Final away goals.
        k_factor: How responsive the rating is to a single result (see module
            constants `K_NATIONAL` / `K_WORLD_CUP` / `K_CLUB`).

    Returns:
        `EloUpdate` with both new ratings and the absolute deltas.
    """
    expected_home = expected_score(home_rating, away_rating)

    if home_score > away_score:
        actual_home = 1.0
    elif home_score < away_score:
        actual_home = 0.0
    else:
        actual_home = 0.5

    home_change = k_factor * (actual_home - expected_home)
    # Symmetric: actual_away = 1 - actual_home, expected_away = 1 - expected_home,
    # so the away delta is the negative of the home delta.
    away_change = -home_change
    return EloUpdate(
        new_home_rating=home_rating + home_change,
        new_away_rating=away_rating + away_change,
        home_change=home_change,
        away_change=away_change,
    )


def k_factor_for(competition_type: str, competition_name: str) -> float:
    """Pick the right K based on competition kind / specific tournament."""
    if competition_type == "national":
        # Heuristic — string match, since FIFA renames "FIFA World Cup" only
        # rarely. We could pin on `competitions.api_football_id` instead in
        # Phase 2 once the catalog is settled.
        if "world cup" in competition_name.lower():
            return K_WORLD_CUP
        return K_NATIONAL
    return K_CLUB


# --- Backfill orchestrator ---


def backfill_elo_ratings(
    session: Session,
    *,
    initial_rating: float = INITIAL_RATING,
) -> int:
    """Walk every finished match in chronological order and write Elo snapshots.

    Idempotent in practice: rows are appended to `elo_ratings`, so re-running
    produces a parallel timeline rather than corrupting existing rows. Callers
    that want a fresh rebuild should `TRUNCATE elo_ratings` first.

    Args:
        session: Active SQLAlchemy session (caller commits).
        initial_rating: Seed value for any team encountered for the first time.

    Returns:
        Number of `elo_ratings` rows written (one per (team, match)).
    """
    rows = _load_finished_matches(session)
    ratings: dict[int, float] = {}
    written = 0

    for row in rows:
        home_rating = ratings.get(row.home_team_id, initial_rating)
        away_rating = ratings.get(row.away_team_id, initial_rating)
        k = k_factor_for(row.competition_type, row.competition_name)
        update = update_ratings(
            home_rating=home_rating,
            away_rating=away_rating,
            home_score=row.home_score,
            away_score=row.away_score,
            k_factor=k,
        )
        ratings[row.home_team_id] = update.new_home_rating
        ratings[row.away_team_id] = update.new_away_rating

        session.add_all(_snapshot_pair(row, update))
        written += 2

    logger.info(
        "elo_backfill_completed", matches_processed=len(rows), rows_written=written
    )
    return written


def _load_finished_matches(session: Session) -> list[_MatchRow]:
    stmt = (
        select(
            Match.id,
            Match.home_team_id,
            Match.away_team_id,
            Match.home_score,
            Match.away_score,
            Match.match_date,
            Competition.competition_type,
            Competition.name,
        )
        .join(Season, Season.id == Match.season_id)
        .join(Competition, Competition.id == Season.competition_id)
        .where(
            Match.status == "finished",
            Match.home_score.is_not(None),
            Match.away_score.is_not(None),
        )
        .order_by(Match.match_date.asc())
    )
    return [
        _MatchRow(
            match_id=row[0],
            home_team_id=row[1],
            away_team_id=row[2],
            home_score=row[3],
            away_score=row[4],
            match_date_iso=row[5].isoformat(),
            competition_type=row[6],
            competition_name=row[7],
        )
        for row in session.execute(stmt).all()
    ]


def _snapshot_pair(row: _MatchRow, update: EloUpdate) -> list[EloRating]:
    rated_at = row.match_date_iso[:10]  # YYYY-MM-DD
    return [
        EloRating(
            team_id=row.home_team_id,
            match_id=row.match_id,
            rating=Decimal(f"{update.new_home_rating:.2f}"),
            rating_change=Decimal(f"{update.home_change:.2f}"),
            rated_at=rated_at,
        ),
        EloRating(
            team_id=row.away_team_id,
            match_id=row.match_id,
            rating=Decimal(f"{update.new_away_rating:.2f}"),
            rating_change=Decimal(f"{update.away_change:.2f}"),
            rated_at=rated_at,
        ),
    ]

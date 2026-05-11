"""Domain-level validation rules.

Pydantic catches malformed types and basic ranges; these helpers enforce
*business* invariants that span multiple fields or require DB lookup. All
public functions raise `DataValidationError` on violation so callers can pick
between hard fail (abort the batch) and soft fail (drop the record + log).
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models.odds_snapshot import OddsSnapshot

# --- Constants (centralized so they're easy to audit / tune) ---

MAX_FUTURE_MATCH_DAYS: int = 365
MAX_REASONABLE_GOALS: int = 30

MIN_DECIMAL_ODDS: Decimal = Decimal("1.01")
# Ceiling matches odds_snapshots Numeric(6,3) column max (999.999) so the
# validator never rejects values the DB would accept. Longshot World Cup
# outright / 1x2 quotes routinely exceed 100.
MAX_DECIMAL_ODDS: Decimal = Decimal("999.999")
ODDS_DEDUP_WINDOW: timedelta = timedelta(hours=1)

MIN_PLAYER_VALUE_EUR: int = 1
MAX_PLAYER_VALUE_EUR: int = 300_000_000

MAX_REASONABLE_XG: Decimal = Decimal("10.00")
POSSESSION_SUM_TOLERANCE: Decimal = Decimal("5.0")  # ±5% around 100


class DataValidationError(ValueError):
    """Raised when domain-level validation fails."""


# --- Match validators ---


def validate_match_fields(
    *,
    match_date: datetime,
    home_score: int | None,
    away_score: int | None,
) -> None:
    """Sanity-check a single match row.

    Raises:
        DataValidationError: If `match_date` is more than
            `MAX_FUTURE_MATCH_DAYS` days in the future, or any score is
            negative / above `MAX_REASONABLE_GOALS`.
    """
    now = datetime.now(UTC)
    if match_date > now + timedelta(days=MAX_FUTURE_MATCH_DAYS):
        raise DataValidationError(
            f"match_date {match_date.isoformat()} is more than "
            f"{MAX_FUTURE_MATCH_DAYS} days in the future"
        )

    for label, score in (("home_score", home_score), ("away_score", away_score)):
        if score is None:
            continue
        if score < 0 or score > MAX_REASONABLE_GOALS:
            raise DataValidationError(
                f"{label}={score} outside [0, {MAX_REASONABLE_GOALS}]"
            )


# --- Odds validators ---


def validate_odds_value(odds: Decimal | float) -> None:
    """Ensure a single decimal odds value is within bookmaker plausibility."""
    value = Decimal(str(odds))
    if value < MIN_DECIMAL_ODDS or value > MAX_DECIMAL_ODDS:
        raise DataValidationError(
            f"odds={value} outside [{MIN_DECIMAL_ODDS}, {MAX_DECIMAL_ODDS}]"
        )


def is_duplicate_odds_snapshot(
    session: Session,
    *,
    match_id: int,
    bookmaker: str,
    market_type: str,
    market_value: str | None,
    snapshot_at: datetime,
) -> bool:
    """Check whether an equivalent snapshot was already stored within the dedup window.

    Two snapshots collide when they share (match, bookmaker, market_type,
    market_value) and the existing one is within `ODDS_DEDUP_WINDOW` *before*
    the new one. This is the cheap pre-write check; the table itself is
    append-only with no UNIQUE constraint, so the caller is the gatekeeper.
    """
    cutoff = snapshot_at - ODDS_DEDUP_WINDOW
    stmt = (
        select(OddsSnapshot.id)
        .where(
            OddsSnapshot.match_id == match_id,
            OddsSnapshot.bookmaker == bookmaker,
            OddsSnapshot.market_type == market_type,
            OddsSnapshot.market_value.is_(market_value)
            if market_value is None
            else OddsSnapshot.market_value == market_value,
            OddsSnapshot.snapshot_at >= cutoff,
            OddsSnapshot.snapshot_at <= snapshot_at,
        )
        .limit(1)
    )
    return session.execute(stmt).first() is not None


# --- Player validators ---


def validate_player_market_value(value_eur: int | None) -> None:
    """Allow None or values inside the (1 EUR, 300 M EUR) plausibility band."""
    if value_eur is None:
        return
    if value_eur < MIN_PLAYER_VALUE_EUR or value_eur > MAX_PLAYER_VALUE_EUR:
        raise DataValidationError(
            f"market_value_eur={value_eur} outside "
            f"[{MIN_PLAYER_VALUE_EUR}, {MAX_PLAYER_VALUE_EUR}]"
        )


# --- Stats validators ---


def validate_team_stats(
    *,
    xg: Decimal | float | None,
    possession: Decimal | float | None,
) -> None:
    """Validate single-team stats (xG plausibility, possession in [0, 100])."""
    if xg is not None:
        xg_val = Decimal(str(xg))
        if xg_val < 0 or xg_val > MAX_REASONABLE_XG:
            raise DataValidationError(
                f"xg={xg_val} outside [0, {MAX_REASONABLE_XG}]"
            )
    if possession is not None:
        poss_val = Decimal(str(possession))
        if poss_val < 0 or poss_val > 100:
            raise DataValidationError(f"possession={poss_val} outside [0, 100]")


def validate_possession_pair(
    home_possession: Decimal | float | None,
    away_possession: Decimal | float | None,
) -> None:
    """Both teams' possession should sum to ~100 (±POSSESSION_SUM_TOLERANCE)."""
    if home_possession is None or away_possession is None:
        return
    total = Decimal(str(home_possession)) + Decimal(str(away_possession))
    if abs(total - Decimal("100")) > POSSESSION_SUM_TOLERANCE:
        raise DataValidationError(
            f"possession sum {total} not within ±{POSSESSION_SUM_TOLERANCE} of 100"
        )

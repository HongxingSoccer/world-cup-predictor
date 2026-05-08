"""GET /api/v1/markets/{match_id} — additional betting markets per match.

The main prediction model is a Poisson goal-distribution. Once we have the
home / away expected goals (lambda_home, lambda_away) plus the existing
BTTS probability, the rest of the common bookmaker markets fall out in
closed form:

* **Both teams to score (BTTS)** — already stored on the prediction row.
* **Corners over/under** — Poisson(lambda_corners) where lambda_corners is
  tuned around the WC average (~10/match) and modulated by the match's
  attacking total (more xG → more corners).
* **Yellow cards over/under** — Poisson(lambda_cards) tuned around 3.5
  with a small bump for mismatches (the trailing team chases the game).
* **First to score** — exact under the Poisson assumption:
  P(home first) = (lambda_home / lambda_total) · (1 − exp(−lambda_total)).
  P(no goal) = exp(−lambda_total).

Out of scope: red cards, penalties, substitutions. Those events are too
sparse per match (≤0.2 / match for penalties; substitutions are
strategic, not statistical) — modeling them with our data would be noise,
and shipping noisy predictions hurts user trust more than skipping the
markets does.
"""
from __future__ import annotations

from math import exp

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from scipy.stats import poisson
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.dependencies import get_db_session
from src.config.settings import settings
from src.models.prediction import Prediction

router = APIRouter(prefix="/api/v1/markets", tags=["markets"])


# ---------------------------------------------------------------------------
# Response shape
# ---------------------------------------------------------------------------


class OverUnderItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    threshold: float
    over: float
    under: float


class FirstToScore(BaseModel):
    model_config = ConfigDict(extra="forbid")

    home: float
    no_goal: float
    away: float


class AdditionalMarketsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    match_id: int
    btts_yes: float
    btts_no: float
    expected_goals: float
    expected_corners: float
    expected_cards: float
    corners: list[OverUnderItem]
    cards: list[OverUnderItem]
    first_to_score: FirstToScore


CORNER_THRESHOLDS: tuple[float, ...] = (8.5, 9.5, 10.5)
CARD_THRESHOLDS: tuple[float, ...] = (3.5, 4.5)


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.get("/{match_id}", response_model=AdditionalMarketsResponse)
def additional_markets(
    match_id: int,
    db_session: Session = Depends(get_db_session),
) -> AdditionalMarketsResponse:
    pred = db_session.execute(
        select(Prediction)
        .where(
            Prediction.match_id == match_id,
            Prediction.model_version == settings.ACTIVE_MODEL_NAME,
        )
        .order_by(Prediction.published_at.desc())
        .limit(1)
    ).scalar_one_or_none()

    if pred is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"no prediction for match {match_id}",
        )

    lam_home = float(pred.lambda_home)
    lam_away = float(pred.lambda_away)
    lam_total = lam_home + lam_away

    btts_yes = float(pred.btts_prob) if pred.btts_prob is not None else _btts_from_lambdas(
        lam_home, lam_away
    )
    btts_no = max(0.0, 1.0 - btts_yes)

    lam_corners = _expected_corners(lam_home, lam_away)
    lam_cards = _expected_cards(lam_home, lam_away)

    return AdditionalMarketsResponse(
        match_id=match_id,
        btts_yes=round(btts_yes, 4),
        btts_no=round(btts_no, 4),
        expected_goals=round(lam_total, 2),
        expected_corners=round(lam_corners, 2),
        expected_cards=round(lam_cards, 2),
        corners=_over_under(lam_corners, CORNER_THRESHOLDS),
        cards=_over_under(lam_cards, CARD_THRESHOLDS),
        first_to_score=_first_to_score(lam_home, lam_away),
    )


# ---------------------------------------------------------------------------
# Math helpers
# ---------------------------------------------------------------------------


def _btts_from_lambdas(lam_home: float, lam_away: float) -> float:
    """Fallback if the prediction row didn't persist btts_prob."""
    p_home_zero = exp(-lam_home)
    p_away_zero = exp(-lam_away)
    return max(0.0, 1.0 - p_home_zero - p_away_zero + p_home_zero * p_away_zero)


def _over_under(lam: float, thresholds: tuple[float, ...]) -> list[OverUnderItem]:
    """For Poisson(lam), P(X > t) and P(X ≤ t). Thresholds are like 8.5, 9.5."""
    out: list[OverUnderItem] = []
    for t in thresholds:
        # Bookmaker thresholds end in .5 so there's no push: X > 8.5 == X >= 9.
        cdf_at_floor = float(poisson.cdf(int(t), lam))
        out.append(
            OverUnderItem(
                threshold=t,
                over=round(1.0 - cdf_at_floor, 4),
                under=round(cdf_at_floor, 4),
            )
        )
    return out


def _first_to_score(lam_home: float, lam_away: float) -> FirstToScore:
    """Exact under independent Poisson goal arrivals."""
    lam_total = lam_home + lam_away
    if lam_total < 1e-9:
        return FirstToScore(home=0.0, no_goal=1.0, away=0.0)
    p_no_goal = exp(-lam_total)
    p_any = 1.0 - p_no_goal
    return FirstToScore(
        home=round((lam_home / lam_total) * p_any, 4),
        no_goal=round(p_no_goal, 4),
        away=round((lam_away / lam_total) * p_any, 4),
    )


def _expected_corners(lam_home: float, lam_away: float) -> float:
    """WC corners average ~10/match. More attacking matches generate more corners."""
    base = 10.0
    xg_total = lam_home + lam_away
    # +0.5 corners per +1 xG above the 2.5 scoring baseline; clamp to a
    # plausible band so weird lambda values can't blow up the model.
    raw = base + 0.5 * (xg_total - 2.5)
    return max(7.0, min(13.0, raw))


def _expected_cards(lam_home: float, lam_away: float) -> float:
    """WC yellows ~3.5/match. Mismatches add a small bump for chase-game tackles."""
    base = 3.5
    diff = abs(lam_home - lam_away)
    raw = base + 0.3 * max(0.0, diff - 0.5)
    return max(2.5, min(5.5, raw))

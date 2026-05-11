"""Per-match odds analyzer: turn (Prediction, OddsSnapshot[]) into value signals.

For each market we care about (1x2, over/under 2.5, btts) we:

    1. Query the latest pre-kickoff snapshot per bookmaker (one row per
       (bookmaker, market_type, market_value) keyed on max(snapshot_at) <
       match_date).
    2. De-vig each bookmaker's basket independently to get per-outcome
       fair probabilities.
    3. For every outcome, pick the best bookmaker (max decimal odds).
    4. Compute EV with the best odds + the same bookmaker's de-vigged prob;
       compute edge against the same basket's fair prob.
    5. Persist (when a prediction_id is supplied) to `odds_analysis` so the
       front-end / notification layer can subscribe.

The analyzer is split into pure-math helpers + the SQL-aware class so unit
tests can exercise the math without a database.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.ml.models.base import PredictionResult
from src.ml.odds.ev_calculator import compute_edge, compute_ev, signal_level
from src.ml.odds.vig_removal import remove_vig
from src.models.match import Match
from src.models.odds_analysis import OddsAnalysis
from src.models.odds_snapshot import OddsSnapshot

logger = structlog.get_logger(__name__)

# Markets covered by the Phase-2 analyzer. The 'over_under' line is fixed at
# 2.5 (the most heavily-traded line); other lines arrive in a Phase-3 sweep.
DEFAULT_OU_LINE: str = "2.5"
SUPPORTED_MARKETS: tuple[str, ...] = ("1x2", "over_under", "btts")


@dataclass(frozen=True)
class OddsAnalysisResult:
    """One value-analysis row, mirroring the `odds_analysis` table."""

    match_id: int
    market_type: str
    market_value: str | None
    outcome: str
    model_prob: float
    best_odds: float
    best_bookmaker: str
    implied_prob: float  # de-vigged prob from the best-odds bookmaker
    ev: float
    edge: float
    signal_level: int


class OddsAnalyzer:
    """Computes value signals for a single match."""

    def __init__(self, session: Session) -> None:
        self._session = session

    # --- Public ---------------------------------------------------------

    def analyze_match(
        self,
        match_id: int,
        prediction: PredictionResult,
        *,
        prediction_id: int | None = None,
    ) -> list[OddsAnalysisResult]:
        """Run analysis on every supported market for `match_id`.

        Args:
            match_id: Internal `matches.id`.
            prediction: Fresh `PredictionResult` for the match.
            prediction_id: When supplied, persist `OddsAnalysis` rows
                referencing this prediction. Pure-math callers can leave it
                None to skip persistence.

        Returns:
            All produced `OddsAnalysisResult`s sorted by `(signal_level desc,
            ev desc)` — front-end-friendly ordering for the value table.
        """
        match = self._session.get(Match, match_id)
        if match is None:
            raise ValueError(f"Match {match_id} not found")

        snapshots = self._latest_snapshots(match_id, match.match_date)
        results: list[OddsAnalysisResult] = []
        results.extend(self._analyze_1x2(match_id, prediction, snapshots))
        results.extend(
            self._analyze_over_under(match_id, prediction, snapshots, line=DEFAULT_OU_LINE)
        )
        results.extend(self._analyze_btts(match_id, prediction, snapshots))

        # Sort: highest signal first, EV breaking ties.
        results.sort(key=lambda r: (-r.signal_level, -r.ev))

        if prediction_id is not None and results:
            self._persist(prediction_id, results)

        return results

    # --- Per-market analyzers (pure once snapshots are in hand) --------

    @staticmethod
    def _analyze_1x2(
        match_id: int,
        prediction: PredictionResult,
        snapshots: Iterable[OddsSnapshot],
    ) -> list[OddsAnalysisResult]:
        relevant = [s for s in snapshots if s.market_type == "1x2"]
        if not relevant:
            return []

        # Per-bookmaker basket → de-vigged probabilities.
        baskets: dict[str, dict[str, float]] = {}
        odds_grids: dict[str, dict[str, float]] = {}
        for snap in relevant:
            basket = {
                "home": float(snap.outcome_home) if snap.outcome_home is not None else 0.0,
                "draw": float(snap.outcome_draw) if snap.outcome_draw is not None else 0.0,
                "away": float(snap.outcome_away) if snap.outcome_away is not None else 0.0,
            }
            if any(v <= 1.0 for v in basket.values()):
                continue
            baskets[snap.bookmaker] = remove_vig(basket)
            odds_grids[snap.bookmaker] = basket

        return _build_results(
            match_id=match_id,
            market_type="1x2",
            market_value=None,
            outcome_to_model_prob={
                "home": prediction.prob_home_win,
                "draw": prediction.prob_draw,
                "away": prediction.prob_away_win,
            },
            baskets=baskets,
            odds_grids=odds_grids,
        )

    @staticmethod
    def _analyze_over_under(
        match_id: int,
        prediction: PredictionResult,
        snapshots: Iterable[OddsSnapshot],
        *,
        line: str,
    ) -> list[OddsAnalysisResult]:
        relevant = [
            s for s in snapshots
            if s.market_type == "over_under" and s.market_value == line
        ]
        if not relevant:
            return []

        baskets: dict[str, dict[str, float]] = {}
        odds_grids: dict[str, dict[str, float]] = {}
        for snap in relevant:
            if snap.outcome_over is None or snap.outcome_under is None:
                continue
            basket = {"over": float(snap.outcome_over), "under": float(snap.outcome_under)}
            if any(v <= 1.0 for v in basket.values()):
                continue
            baskets[snap.bookmaker] = remove_vig(basket)
            odds_grids[snap.bookmaker] = basket

        ou_probs = prediction.over_under_probs.get(line) or {}
        return _build_results(
            match_id=match_id,
            market_type="over_under",
            market_value=line,
            outcome_to_model_prob={
                "over": float(ou_probs.get("over", 0.0)),
                "under": float(ou_probs.get("under", 0.0)),
            },
            baskets=baskets,
            odds_grids=odds_grids,
        )

    @staticmethod
    def _analyze_btts(
        match_id: int,
        prediction: PredictionResult,
        snapshots: Iterable[OddsSnapshot],
    ) -> list[OddsAnalysisResult]:
        relevant = [s for s in snapshots if s.market_type == "btts"]
        if not relevant:
            return []

        baskets: dict[str, dict[str, float]] = {}
        odds_grids: dict[str, dict[str, float]] = {}
        for snap in relevant:
            if snap.outcome_yes is None or snap.outcome_no is None:
                continue
            basket = {"yes": float(snap.outcome_yes), "no": float(snap.outcome_no)}
            if any(v <= 1.0 for v in basket.values()):
                continue
            baskets[snap.bookmaker] = remove_vig(basket)
            odds_grids[snap.bookmaker] = basket

        btts_yes = float(prediction.btts_prob)
        return _build_results(
            match_id=match_id,
            market_type="btts",
            market_value=None,
            outcome_to_model_prob={"yes": btts_yes, "no": 1.0 - btts_yes},
            baskets=baskets,
            odds_grids=odds_grids,
        )

    # --- DB I/O ---------------------------------------------------------

    def _latest_snapshots(
        self, match_id: int, match_date: datetime
    ) -> list[OddsSnapshot]:
        """Latest snapshot per (bookmaker, market_type, market_value) before kickoff.

        We sort by snapshot_at desc and keep the first-seen tuple for each
        (bookmaker, market_type, market_value). Cheap because Phase-1's
        ``idx_odds_match_market`` makes the per-match scan trivial.
        """
        stmt = (
            select(OddsSnapshot)
            .where(
                OddsSnapshot.match_id == match_id,
                OddsSnapshot.snapshot_at < match_date,
            )
            .order_by(OddsSnapshot.snapshot_at.desc(), OddsSnapshot.id.desc())
        )
        seen: set[tuple[str, str, str | None]] = set()
        out: list[OddsSnapshot] = []
        for snap in self._session.execute(stmt).scalars():
            key = (snap.bookmaker, snap.market_type, snap.market_value)
            if key in seen:
                continue
            seen.add(key)
            out.append(snap)
        return out

    def _persist(
        self,
        prediction_id: int,
        results: list[OddsAnalysisResult],
    ) -> None:
        rows = [
            OddsAnalysis(
                match_id=r.match_id,
                prediction_id=prediction_id,
                market_type=r.market_type,
                market_value=r.market_value,
                outcome=r.outcome,
                model_prob=r.model_prob,
                best_odds=r.best_odds,
                best_bookmaker=r.best_bookmaker,
                implied_prob=r.implied_prob,
                ev=r.ev,
                edge=r.edge,
                signal_level=r.signal_level,
            )
            for r in results
        ]
        self._session.add_all(rows)
        self._session.commit()
        logger.info("odds_analysis_persisted", prediction_id=prediction_id, rows=len(rows))


# --- Module-level pure helper ------------------------------------------------


def _build_results(
    *,
    match_id: int,
    market_type: str,
    market_value: str | None,
    outcome_to_model_prob: dict[str, float],
    baskets: dict[str, dict[str, float]],
    odds_grids: dict[str, dict[str, float]],
) -> list[OddsAnalysisResult]:
    """Per outcome: pick the best-odds bookmaker, compute EV/edge/level."""
    if not baskets:
        return []

    out: list[OddsAnalysisResult] = []
    for outcome, model_prob in outcome_to_model_prob.items():
        best_book, best_odds = _best_book_for_outcome(odds_grids, outcome)
        if best_book is None:
            continue
        fair_prob = baskets[best_book].get(outcome, 0.0)
        ev = compute_ev(model_prob, best_odds)
        edge = compute_edge(model_prob, fair_prob)
        out.append(
            OddsAnalysisResult(
                match_id=match_id,
                market_type=market_type,
                market_value=market_value,
                outcome=outcome,
                model_prob=model_prob,
                best_odds=best_odds,
                best_bookmaker=best_book,
                implied_prob=fair_prob,
                ev=ev,
                edge=edge,
                signal_level=signal_level(ev, edge),
            )
        )
    return out


def _best_book_for_outcome(
    odds_grids: dict[str, dict[str, float]], outcome: str
) -> tuple[str | None, float]:
    best_book: str | None = None
    best_odds: float = 0.0
    for book, grid in odds_grids.items():
        odds = grid.get(outcome, 0.0)
        if odds > best_odds:
            best_book = book
            best_odds = odds
    return best_book, best_odds

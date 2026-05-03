"""End-to-end feature assembly pipeline.

Composes the 6 feature calculators into one pass per match. The public
methods follow the spec:

    * compute_for_match(match_id) -> dict[str, Any]
    * compute_batch(match_ids) -> pd.DataFrame
    * save_to_db(match_id, features, labels) -> None
    * export_to_parquet(filepath) -> None

Data-leakage guard: `cutoff_date` defaults to the match's own kickoff time.
Every calculator filters strictly before this datetime, so a feature row for
match M never reflects M's own outcome.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import structlog
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from src.ml.features.attack_defense import AttackDefenseFeatures
from src.ml.features.base import BaseFeatureCalculator
from src.ml.features.elo import EloFeatures
from src.ml.features.h2h import H2HFeatures
from src.ml.features.home_away import HomeAwayFeatures
from src.ml.features.recent_form import RecentFormFeatures
from src.ml.features.team_strength import TeamStrengthFeatures
from src.models.match import Match
from src.models.match_feature import MatchFeature

logger = structlog.get_logger(__name__)

DEFAULT_FEATURE_VERSION: str = "v1"


class FeaturePipeline:
    """Build the full Phase-2 v1 feature vector for one or many matches.

    Attributes:
        FEATURE_VERSION: Stored alongside each row so multiple feature
            schemas can coexist in `match_features`.
    """

    FEATURE_VERSION: str = DEFAULT_FEATURE_VERSION

    def __init__(
        self,
        session: Session,
        *,
        feature_version: str = DEFAULT_FEATURE_VERSION,
    ) -> None:
        self._session = session
        self._feature_version = feature_version
        self._calculators: list[BaseFeatureCalculator] = [
            EloFeatures(session),
            RecentFormFeatures(session),
            AttackDefenseFeatures(session),
            HomeAwayFeatures(session),
            H2HFeatures(session),
            TeamStrengthFeatures(session),
        ]

    # --- Public API ---

    def get_feature_names(self) -> list[str]:
        """Stable list of every feature name in the order calculators run."""
        names: list[str] = []
        for calc in self._calculators:
            names.extend(calc.get_feature_names())
        return names

    def compute_for_match(
        self,
        match_id: int,
        cutoff_date: datetime | None = None,
    ) -> dict[str, Any]:
        """Compute the full feature vector for one match.

        Args:
            match_id: Internal `matches.id`.
            cutoff_date: Override the default cutoff. Defaults to the match's
                own kickoff time, which is the correct cutoff for both training
                (no leakage) and inference (uses everything known before kickoff).
        """
        cutoff = cutoff_date or self._match_kickoff(match_id)
        out: dict[str, Any] = {}
        for calc in self._calculators:
            out.update(calc.compute(match_id, cutoff))
        return out

    def compute_batch(self, match_ids: list[int]) -> pd.DataFrame:
        """Compute features for many matches and return them as a DataFrame.

        Returns:
            DataFrame with `match_id` as the index and one column per feature.
        """
        rows: list[dict[str, Any]] = []
        for mid in match_ids:
            features = self.compute_for_match(mid)
            features["match_id"] = mid
            rows.append(features)
        return pd.DataFrame.from_records(rows).set_index("match_id")

    def save_to_db(
        self,
        match_id: int,
        features: dict[str, Any],
        labels: dict[str, Any] | None = None,
    ) -> None:
        """Upsert one (match_id, feature_version) row into `match_features`.

        Args:
            match_id: Internal match id.
            features: Output of `compute_for_match`.
            labels: ``{"home_score": …, "away_score": …, "result": …}``;
                pass None for upcoming matches that have no result yet.
        """
        row = {
            "match_id": match_id,
            "feature_version": self._feature_version,
            "features": features,
            "label_home_score": (labels or {}).get("home_score"),
            "label_away_score": (labels or {}).get("away_score"),
            "label_result": (labels or {}).get("result"),
            "computed_at": datetime.utcnow(),
        }
        stmt = (
            pg_insert(MatchFeature)
            .values(row)
            .on_conflict_do_update(
                constraint="uq_match_features_match_version",
                set_={k: row[k] for k in ("features", "label_home_score", "label_away_score", "label_result", "computed_at")},
            )
        )
        self._session.execute(stmt)
        self._session.commit()

    def export_to_parquet(self, filepath: str | Path) -> int:
        """Dump every `match_features` row at this version to a Parquet file.

        Args:
            filepath: Destination on disk; parent directory is created if missing.

        Returns:
            Number of rows written.
        """
        target = Path(filepath)
        target.parent.mkdir(parents=True, exist_ok=True)

        stmt = (
            select(
                MatchFeature.match_id,
                MatchFeature.features,
                MatchFeature.label_home_score,
                MatchFeature.label_away_score,
                MatchFeature.label_result,
                MatchFeature.computed_at,
            )
            .where(MatchFeature.feature_version == self._feature_version)
            .order_by(MatchFeature.match_id)
        )
        rows = self._session.execute(stmt).all()
        if not rows:
            logger.warning("export_parquet_empty", filepath=str(target))
            pd.DataFrame().to_parquet(target)
            return 0

        records: list[dict[str, Any]] = []
        for row in rows:
            record: dict[str, Any] = {"match_id": row.match_id}
            record.update(row.features or {})
            record["label_home_score"] = row.label_home_score
            record["label_away_score"] = row.label_away_score
            record["label_result"] = row.label_result
            record["computed_at"] = row.computed_at
            records.append(record)

        df = pd.DataFrame.from_records(records).set_index("match_id")
        df.to_parquet(target)
        logger.info("export_parquet_completed", filepath=str(target), rows=len(df))
        return len(df)

    # --- Internal ---

    def _match_kickoff(self, match_id: int) -> datetime:
        match_date = self._session.execute(
            select(Match.match_date).where(Match.id == match_id)
        ).scalar()
        if match_date is None:
            raise ValueError(f"Match {match_id} not found")
        return match_date

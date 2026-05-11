"""End-to-end prediction orchestrator.

Workflow:

    feature_pipeline.compute_for_match(match_id)
        ↓
    model.predict(features)                       → PredictionResult
        ↓
    confidence_calculator.calculate(...)          → ConfidenceResult
        ↓
    (publish=True only)
        canonical hash  →  insert predictions    → Kafka 'prediction.published'
        odds_analyzer.analyze_match(prediction_id) → write odds_analysis
        ↓
    FullPredictionResult (returned to caller)

Inserts to `predictions` are append-only — the Phase-2 PostgreSQL trigger
rejects UPDATE/DELETE so the published payload + its content_hash stay
tamper-evident. The hash is computed over a canonical, deterministic JSON
projection of the prediction body so rebuilding it from `features_snapshot`
exactly reproduces the original digest.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy.orm import Session

from src.events.producer import EventProducer, NullEventProducer
from src.events.schemas import PredictionPublishedPayload
from src.events.topics import TOPIC_PREDICTION_PUBLISHED
from src.ml.features.pipeline import FeaturePipeline
from src.ml.models.base import BasePredictionModel, PredictionResult
from src.ml.models.confidence import ConfidenceCalculator, ConfidenceResult
from src.ml.odds.analyzer import OddsAnalysisResult, OddsAnalyzer
from src.models.match import Match
from src.models.prediction import Prediction

logger = structlog.get_logger(__name__)

# Number of decimal places used when canonicalising floats for the hash.
# Six is enough to reproduce Pydantic-rendered JSON exactly while shielding us
# from low-bit float drift between platforms / library versions.
HASH_FLOAT_PRECISION: int = 6


@dataclass(frozen=True)
class FullPredictionResult:
    """The artefact returned by `PredictionService.generate_prediction`."""

    match_id: int
    model_version: str
    feature_version: str
    prediction: PredictionResult
    confidence: ConfidenceResult
    features_snapshot: dict[str, Any]
    odds_analysis: list[OddsAnalysisResult] = field(default_factory=list)
    prediction_id: int | None = None
    content_hash: str | None = None
    published_at: datetime | None = None


class PredictionService:
    """Glue layer between feature pipeline / model / odds / persistence / events."""

    def __init__(
        self,
        db_session: Session,
        model: BasePredictionModel,
        feature_pipeline: FeaturePipeline,
        odds_analyzer: OddsAnalyzer,
        confidence_calculator: ConfidenceCalculator,
        producer: EventProducer | None = None,
    ) -> None:
        self._session = db_session
        self._model = model
        self._features = feature_pipeline
        self._odds = odds_analyzer
        self._confidence = confidence_calculator
        self._producer: EventProducer = producer or NullEventProducer()

    # --- Public ---------------------------------------------------------

    def generate_prediction(
        self,
        match_id: int,
        *,
        model_version: str = "latest",
        publish: bool = False,
    ) -> FullPredictionResult:
        """Compute (and optionally persist + broadcast) one prediction.

        Args:
            match_id: Internal `matches.id`.
            model_version: Currently informational — the bound `model`'s own
                `get_model_version()` is the source of truth. Phase 3 will
                use this to pick a specific historical model from MLflow.
            publish: When True, insert into `predictions`, run odds analysis,
                emit a `prediction.published` Kafka event, and populate the
                returned result's `prediction_id` / `content_hash`.

        Returns:
            `FullPredictionResult` covering prediction + confidence
            + (when published) odds analysis.
        """
        match = self._session.get(Match, match_id)
        if match is None:
            raise ValueError(f"Match {match_id} not found")
        if match.status == "cancelled":
            raise ValueError(f"Match {match_id} is cancelled — prediction declined")

        features = self._features.compute_for_match(match_id)
        prediction = self._model.predict(features)
        confidence = self._confidence.calculate(prediction, features)

        full = FullPredictionResult(
            match_id=match_id,
            model_version=self._model.get_model_version(),
            feature_version=self._features.FEATURE_VERSION,
            prediction=prediction,
            confidence=confidence,
            features_snapshot=features,
        )

        if not publish:
            return full
        return self._publish(match, full)

    # --- Internal helpers ----------------------------------------------

    def _publish(
        self, match: Match, full: FullPredictionResult
    ) -> FullPredictionResult:
        """Persist + run odds analysis + emit Kafka. Returns enriched result."""
        prediction = full.prediction
        features = full.features_snapshot
        published_at = datetime.now(UTC)
        content_hash = compute_content_hash(prediction, features, full.confidence)

        row = Prediction(
            match_id=match.id,
            model_version=full.model_version,
            feature_version=full.feature_version,
            prob_home_win=prediction.prob_home_win,
            prob_draw=prediction.prob_draw,
            prob_away_win=prediction.prob_away_win,
            lambda_home=prediction.lambda_home,
            lambda_away=prediction.lambda_away,
            score_matrix=prediction.score_matrix,
            top_scores=prediction.top_scores,
            over_under_probs=prediction.over_under_probs,
            btts_prob=prediction.btts_prob,
            confidence_score=full.confidence.score,
            confidence_level=full.confidence.level,
            features_snapshot=features,
            content_hash=content_hash,
            published_at=published_at,
        )
        self._session.add(row)
        self._session.commit()
        self._session.refresh(row)

        odds_analysis = self._odds.analyze_match(
            match.id, prediction, prediction_id=row.id
        )

        self._emit_event(row, full.confidence, content_hash, published_at)
        self._dispatch_card_fanout(row.id)

        logger.info(
            "prediction_published",
            match_id=match.id,
            prediction_id=row.id,
            model_version=full.model_version,
            confidence=full.confidence.score,
            odds_analysis_count=len(odds_analysis),
        )

        return FullPredictionResult(
            match_id=full.match_id,
            model_version=full.model_version,
            feature_version=full.feature_version,
            prediction=full.prediction,
            confidence=full.confidence,
            features_snapshot=full.features_snapshot,
            odds_analysis=odds_analysis,
            prediction_id=row.id,
            content_hash=content_hash,
            published_at=published_at,
        )

    def _emit_event(
        self,
        row: Prediction,
        confidence: ConfidenceResult,
        content_hash: str,
        published_at: datetime,
    ) -> None:
        try:
            self._producer.publish(
                event_type=TOPIC_PREDICTION_PUBLISHED,
                key=str(row.match_id),
                payload=PredictionPublishedPayload(
                    prediction_id=row.id,
                    match_id=row.match_id,
                    model_version=row.model_version,
                    feature_version=row.feature_version,
                    prob_home_win=float(row.prob_home_win),
                    prob_draw=float(row.prob_draw),
                    prob_away_win=float(row.prob_away_win),
                    confidence_score=row.confidence_score,
                    confidence_level=confidence.level,  # type: ignore[arg-type]
                    content_hash=content_hash,
                    published_at=published_at,
                ),
            )
        except Exception as exc:
            # Kafka hiccup must not undo the DB write — the audit trail is in
            # `predictions` regardless. Log and move on.
            logger.warning("prediction_event_publish_failed", error=str(exc))

    @staticmethod
    def _dispatch_card_fanout(prediction_id: int) -> None:
        """Fire-and-forget per-platform card generation for the new prediction.

        Imported lazily so unit tests don't need the Celery broker URL set
        and so a Celery import error never blocks the publish path. Failures
        are logged-only — Phase 3.5 ops will alert if the task queue is down.
        """
        try:
            from src.config.celery_config import app

            app.send_task("card.fanout_prediction", args=[int(prediction_id)])
        except Exception as exc:
            logger.warning("prediction_card_dispatch_failed", error=str(exc))


# --- Hash helpers ----------------------------------------------------------


def compute_content_hash(
    prediction: PredictionResult,
    features: dict[str, Any],
    confidence: ConfidenceResult | None = None,
) -> str:
    """SHA-256 of the canonical JSON projection of a prediction body.

    Same input → same digest, regardless of dict ordering or float-precision
    jitter (we round to `HASH_FLOAT_PRECISION` decimal places). Mutating any
    captured field changes the digest, which is what the immutability /
    tamper-evidence guarantee on `predictions` relies on.
    """
    payload = {
        "prob_home_win": _round(prediction.prob_home_win),
        "prob_draw": _round(prediction.prob_draw),
        "prob_away_win": _round(prediction.prob_away_win),
        "lambda_home": _round(prediction.lambda_home),
        "lambda_away": _round(prediction.lambda_away),
        "btts_prob": _round(prediction.btts_prob),
        "score_matrix": [[_round(v) for v in row] for row in prediction.score_matrix],
        "over_under_probs": {
            line: {k: _round(v) for k, v in probs.items()}
            for line, probs in prediction.over_under_probs.items()
        },
        "features": {k: _normalize_feature(v) for k, v in sorted(features.items())},
    }
    if confidence is not None:
        payload["confidence_score"] = confidence.score
        payload["confidence_level"] = confidence.level

    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _round(value: float) -> float:
    return round(float(value), HASH_FLOAT_PRECISION)


def _normalize_feature(value: Any) -> Any:
    if isinstance(value, float):
        return _round(value)
    if isinstance(value, (int, str, bool)) or value is None:
        return value
    # Anything richer (lists / dicts) is JSON-serializable; let json.dumps handle it.
    return value

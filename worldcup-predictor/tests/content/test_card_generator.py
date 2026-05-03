"""Unit tests for `src.content.card_generator.CardGenerator`.

Both Playwright (for screenshotting) and S3 (for upload) are dependency-
injected, so the real test path runs against an in-memory storage stub +
a stub renderer that returns canned PNG bytes — no infra required.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import pytest

from src.content.card_generator import (
    CARD_DIMENSIONS,
    CardGenerator,
    PlatformDimensions,
)
from src.content.storage import CardStorage
from src.models.match import Match
from src.models.odds_analysis import OddsAnalysis
from src.models.prediction import Prediction
from src.models.prediction_result import PredictionResult
from src.models.share_card import ShareCard
from src.models.track_record_stat import TrackRecordStat


# A 1×1 PNG (smallest valid bytes — caller doesn't decode it).
_TINY_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d49444154789c6300010000000500010d0a2db40000000049454e44ae426082"
)


class _InMemoryStorage(CardStorage):
    """Records every (key, body) the generator hands it; returns deterministic URLs."""

    def __init__(self) -> None:
        self.uploaded: list[tuple[str, bytes]] = []

    def upload_png(self, key: str, body: bytes) -> str:
        self.uploaded.append((key, body))
        return f"https://test.cdn/wcp-cards/{key}"

    def public_url(self, key: str) -> str:
        return f"https://test.cdn/wcp-cards/{key}"


def _stub_renderer(html: str, width: int, height: int) -> bytes:
    """Pretend Playwright. Records dimensions on the function for assertions."""
    _stub_renderer.last_call = (width, height, html)  # type: ignore[attr-defined]
    return _TINY_PNG


@pytest.fixture()
def storage() -> _InMemoryStorage:
    return _InMemoryStorage()


@pytest.fixture()
def generator(db_session, storage):
    return CardGenerator(
        db_session,
        storage=storage,
        screenshot_renderer=_stub_renderer,
    )


# --- Dimensions table ----------------------------------------------------


def test_card_dimensions_match_spec():
    assert CARD_DIMENSIONS["wechat"] == PlatformDimensions(1080, 1080)
    assert CARD_DIMENSIONS["weibo"] == PlatformDimensions(1200, 675)
    assert CARD_DIMENSIONS["douyin"] == PlatformDimensions(1080, 1920)
    assert CARD_DIMENSIONS["x"] == PlatformDimensions(1200, 675)


# --- prediction card -----------------------------------------------------


def test_generate_prediction_card_renders_uploads_and_persists(
    db_session, make_match, utc, seed_world, generator, storage
):
    match = make_match(utc(2026, 5, 1, 18))
    prediction = _seed_prediction(db_session, match)

    url = generator.generate_prediction_card(prediction.id, "wechat")

    # Storage saw exactly one upload at the WeChat dimensions.
    assert len(storage.uploaded) == 1
    key, body = storage.uploaded[0]
    assert "cards/prediction/wechat/" in key
    assert body == _TINY_PNG
    assert url.endswith(key)

    # Renderer called with the right dimensions.
    width, height, _ = _stub_renderer.last_call  # type: ignore[attr-defined]
    assert (width, height) == (1080, 1080)

    # share_cards row persisted with matching dims.
    card_rows = db_session.query(ShareCard).all()
    assert len(card_rows) == 1
    assert card_rows[0].card_type == "prediction"
    assert card_rows[0].platform == "wechat"
    assert card_rows[0].width == 1080
    assert card_rows[0].height == 1080


def test_generate_prediction_card_unknown_platform_falls_back_to_generic(
    db_session, make_match, utc, seed_world, generator, storage
):
    match = make_match(utc(2026, 5, 1, 18))
    prediction = _seed_prediction(db_session, match)

    generator.generate_prediction_card(prediction.id, "douyin")

    width, height, _ = _stub_renderer.last_call  # type: ignore[attr-defined]
    assert (width, height) == (1080, 1920)


def test_generate_prediction_card_raises_when_prediction_missing(generator):
    with pytest.raises(ValueError, match="not found"):
        generator.generate_prediction_card(99999, "wechat")


# --- red-hit card -------------------------------------------------------


def test_generate_red_hit_card_persists_share_card_row(
    db_session, make_match, utc, seed_world, generator, storage
):
    match = make_match(utc(2026, 5, 1, 18), home_score=2, away_score=1)
    prediction = _seed_prediction(db_session, match)
    result = PredictionResult(
        prediction_id=prediction.id,
        match_id=match.id,
        actual_home_score=2,
        actual_away_score=1,
        result_1x2_hit=True,
        result_score_hit=True,
        pnl_unit=Decimal("1.10"),
        settled_at=datetime.now(timezone.utc),
    )
    db_session.add(result)
    db_session.commit()

    url = generator.generate_red_hit_card(result.id, "weibo")

    assert "cards/red_hit/weibo/" in url
    rows = db_session.query(ShareCard).filter(ShareCard.card_type == "red_hit").all()
    assert len(rows) == 1
    assert rows[0].platform == "weibo"


# --- track-record card --------------------------------------------------


def test_generate_track_record_card_uses_overall_period_row(
    db_session, generator, storage
):
    db_session.add(
        TrackRecordStat(
            stat_type="overall",
            period="all_time",
            total_predictions=120,
            hits=72,
            hit_rate=Decimal("0.6000"),
            total_pnl_units=Decimal("18.40"),
            roi=Decimal("0.1533"),
            current_streak=4,
            best_streak=7,
        )
    )
    db_session.commit()

    url = generator.generate_track_record_card("wechat")

    assert "cards/track_record/wechat/" in url
    # Pull the rendered HTML off the stub renderer to verify the values
    # actually made it into the template.
    _, _, html = _stub_renderer.last_call  # type: ignore[attr-defined]
    assert "60.0" in html      # hit-rate %
    assert "+15.3" in html or "+15.4" in html  # ROI ≈ 15.33%
    assert "连红" in html       # streak label
    assert "4" in html          # current streak


def test_generate_track_record_card_handles_missing_stat_row(db_session, generator):
    # No track_record_stats rows seeded — generator must not crash.
    url = generator.generate_track_record_card("wechat", period="last_7d")
    assert url.startswith("https://test.cdn/")


def _seed_prediction(db_session, match) -> Prediction:
    prediction = Prediction(
        match_id=match.id,
        model_version="poisson_v1",
        feature_version="v1",
        prob_home_win=Decimal("0.55"),
        prob_draw=Decimal("0.25"),
        prob_away_win=Decimal("0.20"),
        lambda_home=Decimal("1.5"),
        lambda_away=Decimal("1.0"),
        score_matrix=[[0.0] * 10 for _ in range(10)],
        top_scores=[{"score": "2-1", "prob": 0.10}, {"score": "1-1", "prob": 0.09}],
        over_under_probs={"2.5": {"over": 0.55, "under": 0.45}},
        btts_prob=Decimal("0.50"),
        confidence_score=72,
        confidence_level="high",
        features_snapshot={},
        content_hash="a" * 64,
        published_at=datetime.now(timezone.utc),
    )
    db_session.add(prediction)
    # Add an odds-analysis row so the prediction context has a signal level.
    db_session.flush()
    db_session.add(
        OddsAnalysis(
            match_id=match.id,
            prediction_id=prediction.id,
            market_type="1x2",
            outcome="home",
            model_prob=Decimal("0.5500"),
            best_odds=Decimal("2.10"),
            best_bookmaker="pinnacle",
            implied_prob=Decimal("0.4762"),
            ev=Decimal("0.1550"),
            edge=Decimal("0.0738"),
            signal_level=2,
        )
    )
    db_session.commit()
    return prediction

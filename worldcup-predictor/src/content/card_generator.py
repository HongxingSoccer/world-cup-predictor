"""Share-card image generator (Phase 3, M6).

Pipeline per request:

    1. Load + shape the data we want to render (via SQLAlchemy).
    2. Render the right Jinja2 template with platform-specific dimensions.
    3. Rasterise the HTML to a PNG via Playwright headless Chromium.
    4. Upload the PNG to S3 / MinIO via `CardStorage`.
    5. Persist a row in `share_cards` and return the public URL.

Playwright + S3 are injected (or built lazily from settings) so unit tests
can mock both without spinning up infrastructure. The runtime helpers all
honour a `screenshot_renderer` callable parameter so headless Chromium isn't
in the critical path of the generator's logic tests.
"""
from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import structlog
from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy.orm import Session

from src.content.storage import CardStorage, build_card_storage
from src.models.match import Match
from src.models.odds_analysis import OddsAnalysis
from src.models.prediction import Prediction
from src.models.prediction_result import PredictionResult
from src.models.share_card import ShareCard
from src.models.team import Team
from src.models.track_record_stat import TrackRecordStat

logger = structlog.get_logger(__name__)

# Platform → (width, height) per the project standards § M6.
@dataclass(frozen=True)
class PlatformDimensions:
    width: int
    height: int


CARD_DIMENSIONS: dict[str, PlatformDimensions] = {
    "wechat":  PlatformDimensions(1080, 1080),
    "weibo":   PlatformDimensions(1200, 675),
    "douyin":  PlatformDimensions(1080, 1920),
    "x":       PlatformDimensions(1200, 675),
    "generic": PlatformDimensions(1200, 675),
}

ALL_PLATFORMS: tuple[str, ...] = ("wechat", "weibo", "douyin", "x")

# Type alias for the "html → png bytes" callable. The default renderer uses
# Playwright; tests pass a stub that returns canned bytes.
ScreenshotRenderer = Callable[[str, int, int], bytes]


_TEMPLATES_DIR: Path = Path(__file__).parent / "templates"


class CardGenerator:
    """Render + persist share cards. Inject `screenshot_renderer` for tests."""

    def __init__(
        self,
        session: Session,
        *,
        storage: CardStorage | None = None,
        screenshot_renderer: ScreenshotRenderer | None = None,
    ) -> None:
        self._session = session
        self._storage: CardStorage = storage or build_card_storage()
        self._render_screenshot: ScreenshotRenderer = (
            screenshot_renderer or _playwright_render_png
        )
        self._jinja = Environment(
            loader=FileSystemLoader(str(_TEMPLATES_DIR)),
            autoescape=select_autoescape(["html"]),
            keep_trailing_newline=False,
        )

    # --- Public methods ---------------------------------------------------

    def generate_prediction_card(
        self, prediction_id: int, platform: str
    ) -> str:
        """Render + upload + persist a prediction card for the given platform."""
        ctx = self._build_prediction_context(prediction_id)
        return self._produce_card(
            template="prediction_card.html",
            card_type="prediction",
            target_id=prediction_id,
            platform=platform,
            context=ctx,
        )

    def generate_red_hit_card(
        self, prediction_result_id: int, platform: str
    ) -> str:
        """Render + upload + persist a red-hit card for the given platform."""
        ctx = self._build_red_hit_context(prediction_result_id)
        return self._produce_card(
            template="red_hit_card.html",
            card_type="red_hit",
            target_id=prediction_result_id,
            platform=platform,
            context=ctx,
        )

    def generate_track_record_card(
        self, platform: str, *, period: str = "all_time"
    ) -> str:
        """Render + upload + persist a track-record card for the given period."""
        ctx = self._build_track_record_context(period)
        target_id = abs(hash((period,))) % (10**9)  # stable-ish id for the row
        return self._produce_card(
            template="track_record_card.html",
            card_type="track_record",
            target_id=target_id,
            platform=platform,
            context=ctx,
        )

    # --- Context builders (pure, easy to test) ---------------------------

    def _build_prediction_context(self, prediction_id: int) -> dict[str, Any]:
        prediction = self._session.get(Prediction, prediction_id)
        if prediction is None:
            raise ValueError(f"Prediction {prediction_id} not found")

        match = self._session.get(Match, prediction.match_id)
        home_team = self._session.get(Team, match.home_team_id) if match else None
        away_team = self._session.get(Team, match.away_team_id) if match else None

        # Highest-signal-level analysis row, if any.
        signal_row = (
            self._session.query(OddsAnalysis)
            .filter(OddsAnalysis.prediction_id == prediction_id)
            .order_by(OddsAnalysis.signal_level.desc())
            .first()
        )

        return {
            "competition": "FIFA World Cup 2026",
            "home_team": home_team.name if home_team else "Home",
            "away_team": away_team.name if away_team else "Away",
            "kickoff_text": (
                match.match_date.strftime("%Y-%m-%d %H:%M UTC")
                if match and match.match_date
                else ""
            ),
            "prob_home_win": float(prediction.prob_home_win),
            "prob_draw": float(prediction.prob_draw),
            "prob_away_win": float(prediction.prob_away_win),
            "confidence_score": int(prediction.confidence_score),
            "signal_level": int(signal_row.signal_level) if signal_row else 0,
            "generated_at": _now_text(),
        }

    def _build_red_hit_context(self, prediction_result_id: int) -> dict[str, Any]:
        result = self._session.get(PredictionResult, prediction_result_id)
        if result is None:
            raise ValueError(f"PredictionResult {prediction_result_id} not found")

        prediction = self._session.get(Prediction, result.prediction_id)
        match = self._session.get(Match, result.match_id)
        home_team = self._session.get(Team, match.home_team_id) if match else None
        away_team = self._session.get(Team, match.away_team_id) if match else None

        predicted_label = _label_1x2_from_prediction(prediction) if prediction else "?"
        actual_label = _label_1x2_from_score(
            result.actual_home_score, result.actual_away_score
        )

        # Streak read from the cached track record (overall × all_time).
        streak = self._lookup_streak("overall", "all_time")

        return {
            "competition": "FIFA World Cup 2026",
            "home_team": home_team.name if home_team else "Home",
            "away_team": away_team.name if away_team else "Away",
            "home_score": result.actual_home_score,
            "away_score": result.actual_away_score,
            "predicted_label": predicted_label,
            "actual_label": actual_label,
            "streak": streak,
            "generated_at": _now_text(),
        }

    def _build_track_record_context(self, period: str) -> dict[str, Any]:
        row = (
            self._session.query(TrackRecordStat)
            .filter(
                TrackRecordStat.stat_type == "overall",
                TrackRecordStat.period == period,
            )
            .first()
        )
        if row is None:
            return _empty_track_record_context(period)

        hit_rate = float(row.hit_rate or Decimal("0"))
        roi = float(row.roi or Decimal("0"))
        total_pnl = float(row.total_pnl_units or Decimal("0"))
        return {
            "period_label": _period_label(period),
            "total_predictions": row.total_predictions,
            "hits": row.hits,
            "hit_rate_pct": hit_rate * 100.0,
            "roi_pct": roi * 100.0,
            "total_pnl_units": total_pnl,
            "streak": row.current_streak,
            "best_streak": row.best_streak,
            "generated_at": _now_text(),
        }

    # --- Render + upload + persist (single chokepoint) -------------------

    def _produce_card(
        self,
        *,
        template: str,
        card_type: str,
        target_id: int,
        platform: str,
        context: dict[str, Any],
    ) -> str:
        dims = CARD_DIMENSIONS.get(platform, CARD_DIMENSIONS["generic"])
        full_context = {**context, "width": dims.width, "height": dims.height, "platform": platform}
        html = self._jinja.get_template(template).render(**full_context)
        png = self._render_screenshot(html, dims.width, dims.height)

        key = f"cards/{card_type}/{platform}/{target_id}-{int(time.time())}.png"
        url = self._storage.upload_png(key, png)

        self._session.add(
            ShareCard(
                card_type=card_type,
                target_id=target_id,
                platform=platform,
                image_url=url,
                width=dims.width,
                height=dims.height,
            )
        )
        self._session.commit()
        logger.info(
            "card_generated",
            card_type=card_type,
            target_id=target_id,
            platform=platform,
            width=dims.width,
            height=dims.height,
        )
        return url

    def _lookup_streak(self, stat_type: str, period: str) -> int:
        row = (
            self._session.query(TrackRecordStat)
            .filter(
                TrackRecordStat.stat_type == stat_type,
                TrackRecordStat.period == period,
            )
            .first()
        )
        return int(row.current_streak) if row else 0


# --- Module helpers --------------------------------------------------------


def _now_text() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")


def _label_1x2_from_prediction(prediction: Prediction) -> str:
    home = float(prediction.prob_home_win)
    draw = float(prediction.prob_draw)
    away = float(prediction.prob_away_win)
    if home >= draw and home >= away:
        return "主胜"
    if away > home and away >= draw:
        return "客胜"
    return "平局"


def _label_1x2_from_score(home: int, away: int) -> str:
    if home > away:
        return "主胜"
    if home < away:
        return "客胜"
    return "平局"


def _period_label(period: str) -> str:
    return {
        "all_time": "全周期",
        "last_30d": "近30天",
        "last_7d": "近7天",
        "worldcup": "世界杯",
    }.get(period, period)


def _empty_track_record_context(period: str) -> dict[str, Any]:
    return {
        "period_label": _period_label(period),
        "total_predictions": 0,
        "hits": 0,
        "hit_rate_pct": 0.0,
        "roi_pct": 0.0,
        "total_pnl_units": 0.0,
        "streak": 0,
        "best_streak": 0,
        "generated_at": _now_text(),
    }


def _playwright_render_png(html: str, width: int, height: int) -> bytes:
    """Default screenshot renderer — Playwright headless Chromium.

    Lazily imported so tests + non-card workers don't pay the import cost.
    Raises a clear error when Playwright isn't installed; the caller can
    swap in a stub renderer to avoid the dependency.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError(
            "playwright is not installed; run `pip install playwright && "
            "playwright install chromium` or pass a stub `screenshot_renderer`"
        ) from exc

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            context = browser.new_context(viewport={"width": width, "height": height})
            page = context.new_page()
            page.set_content(html, wait_until="networkidle", timeout=20_000)
            return page.screenshot(full_page=False, type="png")
        finally:
            browser.close()

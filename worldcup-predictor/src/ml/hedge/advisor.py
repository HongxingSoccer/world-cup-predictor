"""Combine calculator output with ML probabilities to emit a recommendation.

§5.3 decision tree, expressed as four discrete branches over the (signs of)
original-side EV and hedge-side EV. The advisor never short-circuits the
calculator — it just adds a verdict label + reasoning string.

When the ML prediction service is unreachable or returns no probabilities for
this match, the advisor degrades to ``recommendation = None`` and surfaces
the math-only result instead of guessing. That preserves the design-doc
invariant that the *calculator* is always available; only the *intelligent
advisor* layer needs a model.
"""
from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

from .schemas import AssessmentLabel

logger = logging.getLogger(__name__)


# §5.3 reasoning strings — wired verbatim to keep i18n surface minimal.
_REASON: dict[str, str] = {
    "建议对冲": "模型显示原始下注方向 EV 已转负,建议对冲锁定利润",
    "对冲有价值": "对冲操作本身也是一笔有价值的交易,双重正期望",
    "谨慎对冲": "对冲会牺牲正期望,仅在风险控制需要时才建议",
    "不建议对冲": "保持原始持仓是最优策略",
    "no_probs": "模型概率不可用,仅提供数学对冲计算",
}


class HedgeAdvisor:
    """Math-aware advisor; pure when probabilities are supplied directly."""

    def __init__(self, prediction_service: Any | None = None) -> None:
        """
        :param prediction_service: an ml-api-internal prediction client with
            ``predict_probabilities(match_id, market, outcome) -> Decimal``.
            ``None`` is the canonical test-mode value — callers must then
            pass ``model_prob_original`` / ``model_prob_hedge`` to
            :meth:`assess` directly.
        """
        self.prediction_service = prediction_service

    def assess(
        self,
        match_id: int,
        original_outcome: str,
        original_odds: Decimal,
        hedge_outcome: str,
        hedge_odds: Decimal,
        *,
        model_prob_original: Decimal | None = None,
        model_prob_hedge: Decimal | None = None,
        original_market: str | None = None,
    ) -> dict[str, Any]:
        """Decide a recommendation + reasoning for a single (original, hedge) pair.

        Returns a dict with keys::

            model_prob_original, model_prob_hedge, original_ev, hedge_ev,
            recommendation (None when probs unavailable), reasoning

        EVs are kept at 4 decimal places (matches the ``ev_of_hedge`` DB column).
        """
        # --- resolve probabilities ---------------------------------------
        if (
            model_prob_original is None
            or model_prob_hedge is None
        ) and self.prediction_service is not None and original_market is not None:
            try:
                if model_prob_original is None:
                    model_prob_original = self._fetch_prob(
                        match_id, original_market, original_outcome
                    )
                if model_prob_hedge is None:
                    model_prob_hedge = self._fetch_prob(
                        match_id, original_market, hedge_outcome
                    )
            except Exception as exc:
                logger.warning(
                    "advisor_prob_fetch_failed",
                    extra={"match_id": match_id, "error": str(exc)},
                )

        # --- math-only fallback ------------------------------------------
        if model_prob_original is None or model_prob_hedge is None:
            return {
                "model_prob_original": model_prob_original,
                "model_prob_hedge": model_prob_hedge,
                "original_ev": None,
                "hedge_ev": None,
                "recommendation": None,
                "reasoning": _REASON["no_probs"],
            }

        original_ev = (model_prob_original * original_odds - Decimal("1")).quantize(
            Decimal("0.0001")
        )
        hedge_ev = (model_prob_hedge * hedge_odds - Decimal("1")).quantize(
            Decimal("0.0001")
        )

        # --- §5.3 decision tree ------------------------------------------
        rec: AssessmentLabel
        if original_ev < 0 and hedge_ev >= 0:
            rec = "建议对冲"
        elif original_ev > 0 and hedge_ev > 0:
            rec = "对冲有价值"
        elif original_ev > 0 and hedge_ev < 0:
            rec = "谨慎对冲"
        else:
            # Catches:
            #   original_ev <= 0 AND hedge_ev < 0  (both bad — original still less bad)
            #   the original_ev == 0 boundary defaults to "不建议对冲"
            rec = "不建议对冲"

        return {
            "model_prob_original": model_prob_original,
            "model_prob_hedge": model_prob_hedge,
            "original_ev": original_ev,
            "hedge_ev": hedge_ev,
            "recommendation": rec,
            "reasoning": _REASON[rec],
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _fetch_prob(
        self, match_id: int, market: str, outcome: str
    ) -> Decimal | None:
        """Call the prediction service. Returns None if it has no entry."""
        if self.prediction_service is None:  # pragma: no cover — caller-checked
            return None
        prob = self.prediction_service.predict_probabilities(
            match_id=match_id, market=market, outcome=outcome
        )
        if prob is None:
            return None
        return Decimal(str(prob)).quantize(Decimal("0.0001"))


__all__ = ["HedgeAdvisor"]

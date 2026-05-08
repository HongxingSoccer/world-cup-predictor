"""AI Chinese match-report generator (Phase 4 v2 — design-aligned).

Implements ``docs/design/06_Phase4_ModelEvolution.md §4``: an 8-section
800-1500 字 Chinese pre-match analysis. The default LLM is Claude Sonnet 4
with GPT-4o-mini as a fallback (matching the design "model selection" /
"备用模型" rows). Every section is required:

    1. 比赛概览        2. 近况对比        3. 伤病情况
    4. 历史交锋        5. 数据分析        6. 模型判断
    7. 赔ردة洞察       8. 总结与建议（含免责声明）

The provider abstraction is intentionally narrow — production callers
inject a custom :class:`LLMClient` (or a mock in tests) instead of relying
on env configuration. The default OpenAI/Anthropic implementations lazily
import their SDKs so neither library is mandatory at runtime.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Protocol

import structlog

logger = structlog.get_logger(__name__)

DEFAULT_SYSTEM_PROMPT = (
    "你是一位资深足球数据分析师，擅长用通俗的中文为竞猜用户提供赛前分析。"
    "风格要求：专业但不晦涩，用数据说话，避免主观臆断；禁止使用『稳赚』『必赢』"
    "等诱导性用语；禁止使用 emoji。输出全文为简体中文，使用中文标点。"
)
REPORT_SECTIONS: tuple[str, ...] = (
    "比赛概览",
    "近况对比",
    "伤病情况",
    "历史交锋",
    "数据分析",
    "模型判断",
    "赔率洞察",
    "总结与建议",
)
DISCLAIMER: str = "免责声明：本平台仅提供数据分析参考，不构成任何投注建议。"

# Defaults from design §4.3.2.
DEFAULT_PRIMARY_MODEL: str = "claude-sonnet-4-20250514"
DEFAULT_FALLBACK_MODEL: str = "gpt-4o-mini"
DEFAULT_TEMPERATURE: float = 0.3
DEFAULT_MAX_TOKENS: int = 2000
TARGET_MIN_CHARS: int = 800
TARGET_MAX_CHARS: int = 1500


@dataclass(frozen=True)
class MatchReportContext:
    """All variables injected into the LLM prompt for one match."""

    home_team: str
    away_team: str
    competition: str
    kickoff_iso: str
    prob_home_win: float
    prob_draw: float
    prob_away_win: float
    lambda_home: float
    lambda_away: float
    top_scores: list[dict[str, float]] = field(default_factory=list)
    value_signals: list[str] = field(default_factory=list)
    home_recent_form: str = ""
    away_recent_form: str = ""
    home_injuries: list[str] = field(default_factory=list)
    away_injuries: list[str] = field(default_factory=list)
    h2h_summary: str = ""
    home_xg_avg: Optional[float] = None
    away_xg_avg: Optional[float] = None
    market_implied: Optional[dict[str, float]] = None  # {home,draw,away}
    importance_note: str = ""  # e.g. "主队必须获胜才能出线"


# ---------------------------------------------------------------------------
# Client abstraction
# ---------------------------------------------------------------------------


class LLMClient(Protocol):
    """Minimal chat-completion contract; implementations live in this module."""

    name: str  # short identifier, e.g. "claude-sonnet-4-20250514"

    def complete(self, system: str, user: str, *, max_tokens: int) -> str:
        """Return the assistant message text."""


class FallbackLLMClient:
    """Try the primary client; on exception, fall back to the next one.

    Mirrors the design's "Claude API 不可用时 fallback GPT-4o-mini" requirement.
    The clients are tried in order until one returns non-empty text.
    """

    def __init__(self, clients: list[LLMClient]) -> None:
        if not clients:
            raise ValueError("FallbackLLMClient requires at least one client")
        self._clients = clients
        self.name = ",".join(c.name for c in clients)

    def complete(self, system: str, user: str, *, max_tokens: int) -> str:
        last_err: Optional[Exception] = None
        for client in self._clients:
            try:
                text = client.complete(system, user, max_tokens=max_tokens)
                if text:
                    return text
            except Exception as exc:  # noqa: BLE001 — try next client
                last_err = exc
                logger.warning("llm_client_failed", name=client.name, error=str(exc))
        raise RuntimeError(
            f"all LLM clients failed; last error: {last_err!r}"
        )


class StubLLMClient:
    """Deterministic placeholder used when no real LLM credentials are configured.

    The Celery report task (`generate_match_report`) MUST receive *some*
    `LLMClient` instance — without one it raises. Pre-launch we don't have
    Claude / OpenAI keys yet but want the task pipeline (settlement →
    report fan-out → push) to still execute end-to-end so we can shake out
    plumbing bugs. This client returns a templated 8-section report based
    on the structured probabilities the caller already has, so generated
    reports look real enough to validate the renderer + persistence path.

    Wire-up: :func:`build_llm_client_from_settings` returns one of these
    when the operator hasn't set ``ANTHROPIC_API_KEY`` /
    ``OPENAI_API_KEY``. Once a real key lands the same factory swaps in
    the production client without touching call sites.
    """

    name = "stub-llm"

    def complete(self, system: str, user: str, *, max_tokens: int) -> str:
        # The user prompt embeds the team names + key probs in a structured
        # JSON-like dump (built by AIReportGenerator). Pulling them back out
        # by string-search keeps this stub independent of the real prompt
        # format — when the format evolves the report just degrades to the
        # generic template, never crashes.
        home = _scan(user, "home_team")
        away = _scan(user, "away_team")
        prob = _scan(user, "prob_home_win")
        sections = "\n\n".join(
            f"## {idx + 1}. {name}\n本节深度分析将在赛前 24 小时内由 AI 模型生成并发布。"
            for idx, name in enumerate(REPORT_SECTIONS)
        )
        header = (
            f"# {home or '主队'} vs {away or '客队'} · 赛前分析\n"
            f"模型主胜概率约 {prob or '—'}。完整 8 章节中文分析将在赛前 24 小时内推送。\n"
        )
        return f"{header}\n{sections}\n\n{DISCLAIMER}"


def _scan(text: str, key: str) -> Optional[str]:
    """Best-effort key:value extractor for the StubLLMClient prompt scan."""
    needle = f'"{key}"'
    idx = text.find(needle)
    if idx < 0:
        return None
    tail = text[idx + len(needle):]
    colon = tail.find(":")
    if colon < 0:
        return None
    fragment = tail[colon + 1:].lstrip()
    end = 0
    while end < len(fragment) and fragment[end] not in {",", "\n", "}", "]"}:
        end += 1
    return fragment[:end].strip().strip('"').strip("'") or None


def build_llm_client_from_settings() -> LLMClient:
    """Return the best LLM client available given the current env config.

    Order of preference: real Anthropic → OpenAI-compatible → stub. This
    keeps the production path identical (FallbackLLMClient with both real
    clients) when keys are configured, and makes dev / pre-launch builds
    work without any keys at all.
    """
    from src.config.settings import settings  # local — avoid import cycles

    anthropic_key = getattr(settings, "ANTHROPIC_API_KEY", None) or None
    openai_key = getattr(settings, "OPENAI_API_KEY", None) or None
    openai_base = getattr(settings, "OPENAI_BASE_URL", None) or None
    primary_model = (
        getattr(settings, "LLM_PRIMARY_MODEL", None) or DEFAULT_PRIMARY_MODEL
    )
    fallback_model = (
        getattr(settings, "LLM_FALLBACK_MODEL", None) or DEFAULT_FALLBACK_MODEL
    )

    real: list[LLMClient] = []
    if anthropic_key:
        real.append(AnthropicClient(api_key=anthropic_key, model=primary_model))
    if openai_key:
        real.append(
            OpenAICompatibleClient(
                api_key=openai_key, base_url=openai_base, model=fallback_model
            )
        )
    if real:
        return FallbackLLMClient(real) if len(real) > 1 else real[0]
    logger.info("llm_using_stub_client_no_keys_configured")
    return StubLLMClient()


class OpenAICompatibleClient:
    """OpenAI-compatible client; works with OpenAI / DeepSeek / Qwen / GPT-4o-mini."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: Optional[str] = None,
        model: str = DEFAULT_FALLBACK_MODEL,
        temperature: float = DEFAULT_TEMPERATURE,
    ) -> None:
        if not api_key:
            raise ValueError("LLM api_key is required")
        self._api_key = api_key
        self._base_url = base_url
        self._temperature = temperature
        self.name = model

    def complete(self, system: str, user: str, *, max_tokens: int) -> str:
        from openai import OpenAI  # noqa: WPS433 — lazy import

        client = OpenAI(api_key=self._api_key, base_url=self._base_url)
        response = client.chat.completions.create(
            model=self.name,
            temperature=self._temperature,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return (response.choices[0].message.content or "").strip()


class AnthropicClient:
    """Anthropic Messages API client (Claude Sonnet 4 default)."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str = DEFAULT_PRIMARY_MODEL,
        temperature: float = DEFAULT_TEMPERATURE,
    ) -> None:
        if not api_key:
            raise ValueError("Anthropic api_key is required")
        self._api_key = api_key
        self._temperature = temperature
        self.name = model

    def complete(self, system: str, user: str, *, max_tokens: int) -> str:
        from anthropic import Anthropic  # noqa: WPS433 — lazy import

        client = Anthropic(api_key=self._api_key)
        response = client.messages.create(
            model=self.name,
            max_tokens=max_tokens,
            temperature=self._temperature,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        # Concatenate any text blocks the API returns.
        parts = [
            getattr(block, "text", "") for block in (response.content or [])
        ]
        return "".join(parts).strip()


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------


class AIReportGenerator:
    """Render the prompt then call the LLM client; tiny enough to mock cleanly."""

    def __init__(
        self,
        client: LLMClient,
        *,
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        target_min_chars: int = TARGET_MIN_CHARS,
        target_max_chars: int = TARGET_MAX_CHARS,
    ) -> None:
        self._client = client
        self._system_prompt = system_prompt
        self._max_tokens = max_tokens
        self._target_min = target_min_chars
        self._target_max = target_max_chars

    def generate(self, ctx: MatchReportContext) -> str:
        """Build the user prompt + invoke LLM; returns the report text."""
        prompt = build_user_prompt(
            ctx, target_min=self._target_min, target_max=self._target_max
        )
        report = self._client.complete(
            self._system_prompt, prompt, max_tokens=self._max_tokens
        )
        if not report:
            raise RuntimeError("LLM returned empty content")
        if DISCLAIMER not in report:
            report = f"{report}\n\n{DISCLAIMER}"
        logger.info(
            "ai_report_generated",
            home=ctx.home_team,
            away=ctx.away_team,
            length=len(report),
            model=getattr(self._client, "name", "unknown"),
        )
        return report


# ---------------------------------------------------------------------------
# Prompt builder (pure function — easy to snapshot-test)
# ---------------------------------------------------------------------------


def build_user_prompt(
    ctx: MatchReportContext,
    *,
    target_min: int = TARGET_MIN_CHARS,
    target_max: int = TARGET_MAX_CHARS,
) -> str:
    """Render the user-message body."""
    top_scores_str = ", ".join(
        f"{s['score']} ({float(s['prob']) * 100:.1f}%)" for s in ctx.top_scores[:5]
    ) or "无"
    signals_str = "；".join(ctx.value_signals) if ctx.value_signals else "无明显价值信号"
    home_inj = "、".join(ctx.home_injuries) if ctx.home_injuries else "无重要缺阵"
    away_inj = "、".join(ctx.away_injuries) if ctx.away_injuries else "无重要缺阵"
    market = ctx.market_implied or {}
    market_str = (
        f"主胜 {market.get('home', 0) * 100:.1f}% / "
        f"平 {market.get('draw', 0) * 100:.1f}% / "
        f"客胜 {market.get('away', 0) * 100:.1f}%"
        if market
        else "暂无可比对市场赔率"
    )
    sections_brief = "\n".join(
        f"{idx + 1}. {name}" for idx, name in enumerate(REPORT_SECTIONS)
    )
    return (
        f"【比赛信息】\n"
        f"- 比赛: {ctx.home_team} vs {ctx.away_team}\n"
        f"- 赛事: {ctx.competition}\n"
        f"- 开球时间: {ctx.kickoff_iso}\n"
        f"- 重要性: {ctx.importance_note or '常规赛事'}\n"
        f"\n【模型预测】\n"
        f"- 胜平负概率: 主胜 {ctx.prob_home_win * 100:.1f}% / 平 "
        f"{ctx.prob_draw * 100:.1f}% / 客胜 {ctx.prob_away_win * 100:.1f}%\n"
        f"- 预期进球 (λ): 主队 {ctx.lambda_home:.2f}, 客队 {ctx.lambda_away:.2f}\n"
        f"- Top5 比分: {top_scores_str}\n"
        f"\n【近况】\n"
        f"- 主队 ({ctx.home_team}): {ctx.home_recent_form or 'N/A'}\n"
        f"- 客队 ({ctx.away_team}): {ctx.away_recent_form or 'N/A'}\n"
        f"\n【伤病】\n"
        f"- 主队: {home_inj}\n"
        f"- 客队: {away_inj}\n"
        f"\n【历史交锋】\n"
        f"{ctx.h2h_summary or '无可用历史数据'}\n"
        f"\n【数据指标】\n"
        f"- 主队近5场 xG 均值: "
        f"{ctx.home_xg_avg if ctx.home_xg_avg is not None else 'N/A'}\n"
        f"- 客队近5场 xG 均值: "
        f"{ctx.away_xg_avg if ctx.away_xg_avg is not None else 'N/A'}\n"
        f"\n【赔率信号】\n"
        f"- 市场隐含概率: {market_str}\n"
        f"- 模型识别的价值信号: {signals_str}\n"
        f"\n【输出要求】\n"
        f"请严格按照以下 8 段结构输出，每段 100-200 字，"
        f"全文 {target_min}-{target_max} 字。每段以 ## 段号 + 标题 开头。\n"
        f"{sections_brief}\n"
        f"\n最后一段必须包含免责声明: {DISCLAIMER}\n"
    )

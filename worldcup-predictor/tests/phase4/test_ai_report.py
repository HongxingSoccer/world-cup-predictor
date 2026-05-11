"""Unit tests for src.content.ai_report."""
from __future__ import annotations

import pytest

from src.content.ai_report import (
    DISCLAIMER,
    REPORT_SECTIONS,
    AIReportGenerator,
    FallbackLLMClient,
    MatchReportContext,
    OpenAICompatibleClient,
    StubLLMClient,
    build_llm_client_from_settings,
    build_user_prompt,
)


class _FakeClient:
    def __init__(self, response: str = "中文报告内容", *, name: str = "fake", fail: bool = False) -> None:
        self.response = response
        self.name = name
        self.fail = fail
        self.calls: list[tuple[str, str, int]] = []

    def complete(self, system: str, user: str, *, max_tokens: int) -> str:
        self.calls.append((system, user, max_tokens))
        if self.fail:
            raise RuntimeError(f"{self.name} unavailable")
        return self.response


def _ctx() -> MatchReportContext:
    return MatchReportContext(
        home_team="阿根廷",
        away_team="法国",
        competition="2026 世界杯小组赛",
        kickoff_iso="2026-06-15T20:00:00Z",
        prob_home_win=0.45,
        prob_draw=0.27,
        prob_away_win=0.28,
        lambda_home=1.6,
        lambda_away=1.2,
        top_scores=[
            {"score": "1-1", "prob": 0.13},
            {"score": "2-1", "prob": 0.11},
        ],
        value_signals=["主胜赔率高于模型估计 8%"],
        home_recent_form="近 5 场 4 胜 1 平",
        away_recent_form="近 5 场 3 胜 2 负",
    )


def test_build_user_prompt_contains_key_fields():
    prompt = build_user_prompt(_ctx())
    assert "阿根廷" in prompt
    assert "法国" in prompt
    assert "1-1" in prompt
    assert "主胜赔率" in prompt
    # All 8 design sections must be listed in the output requirements.
    for section in REPORT_SECTIONS:
        assert section in prompt


def test_generator_appends_disclaimer_when_missing():
    fake = _FakeClient(response="这是一段不少于十个字的中文分析文本。")
    gen = AIReportGenerator(fake)
    output = gen.generate(_ctx())
    assert DISCLAIMER in output
    assert output.startswith("这是一段不少于十个字的中文分析文本。")
    assert len(fake.calls) == 1


def test_generator_keeps_disclaimer_when_already_present():
    body = f"报告内容。{DISCLAIMER}"
    fake = _FakeClient(response=body)
    gen = AIReportGenerator(fake)
    assert gen.generate(_ctx()) == body


def test_fallback_client_falls_through_to_secondary():
    primary = _FakeClient(name="claude", fail=True)
    secondary = _FakeClient(response="备用输出", name="gpt-4o-mini")
    fb = FallbackLLMClient([primary, secondary])
    out = fb.complete("sys", "user", max_tokens=100)
    assert out == "备用输出"
    assert len(primary.calls) == 1
    assert len(secondary.calls) == 1


def test_fallback_client_raises_when_all_fail():
    fb = FallbackLLMClient([_FakeClient(name="a", fail=True), _FakeClient(name="b", fail=True)])
    with pytest.raises(RuntimeError):
        fb.complete("sys", "user", max_tokens=100)


def test_generator_raises_on_empty_response():
    fake = _FakeClient(response="")
    gen = AIReportGenerator(fake)
    with pytest.raises(RuntimeError):
        gen.generate(_ctx())


def test_openai_client_validates_api_key():
    with pytest.raises(ValueError):
        OpenAICompatibleClient(api_key="")


def test_stub_client_returns_eight_section_placeholder():
    """Stub mode (no LLM keys) must still output a renderable 8-section body."""
    client = StubLLMClient()
    body = client.complete(
        system="sys",
        user='{"home_team": "Brazil", "away_team": "Argentina", "prob_home_win": 0.55}',
        max_tokens=2000,
    )
    for section in REPORT_SECTIONS:
        assert section in body
    assert "Brazil" in body
    assert "Argentina" in body
    assert DISCLAIMER in body


def test_settings_factory_returns_stub_when_no_keys(monkeypatch):
    """Pre-launch builds (no env keys) get the stub via the factory."""
    from src.config.settings import settings

    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")
    client = build_llm_client_from_settings()
    assert isinstance(client, StubLLMClient)


def test_generator_renders_with_stub_client():
    """End-to-end: AIReportGenerator + StubLLMClient yields a valid report."""
    body = AIReportGenerator(StubLLMClient()).generate(_ctx())
    for section in REPORT_SECTIONS:
        assert section in body
    assert DISCLAIMER in body

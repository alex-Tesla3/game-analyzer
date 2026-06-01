"""Tests for LLM JSON parsing and scenario report merge."""

from __future__ import annotations

import pytest

from src.services.llm_client import clean_llm_report_text, parse_json_from_llm
from src.services.scenario_ai import _merge_llm_into_report, _rule_breakdown_report


def test_parse_json_from_llm_markdown_fence():
    raw = """```json
{
  "executive_summary": "《War Thunder》代表硬核模拟射击品类。",
  "sections": [{"title": "核心循环", "content": "载具对战驱动留存。"}]
}
```"""
    parsed = parse_json_from_llm(raw)
    assert parsed is not None
    assert "War Thunder" in parsed["executive_summary"]
    assert len(parsed["sections"]) == 1


def test_parse_json_from_llm_prose_wrapper():
    raw = (
        "以下是分析结果：\n"
        '{"executive_summary":"样本好评率整体稳定","sections":[{"title":"趋势","content":"Dota 2 上升"}]}\n'
        "希望有帮助。"
    )
    parsed = parse_json_from_llm(raw)
    assert parsed is not None
    assert "稳定" in parsed["executive_summary"]


def test_clean_llm_report_text_strips_json_blob():
    polluted = '```json\n{"executive_summary":"干净的摘要文本","sections":[]}\n```'
    assert clean_llm_report_text(polluted) == "干净的摘要文本"


def test_merge_llm_never_injects_raw_json():
    base = _rule_breakdown_report(
        [{"name": "War Thunder", "genre": "Simulation"}],
        [{}],
    )
    raw = """```json
{
  "executive_summary": "结构化摘要",
  "sections": [{"title": "商业化", "content": "免费+内购"}]
}
```"""
    merged, using_llm, err = _merge_llm_into_report(base, raw)
    assert using_llm is True
    assert err is None
    assert merged["executive_summary"] == "结构化摘要"
    assert "```json" not in merged["executive_summary"]
    assert merged["sections"][0]["title"] == "商业化"


def test_merge_llm_fallback_on_unparseable():
    base = _rule_breakdown_report(
        [{"name": "CS2", "genre": "FPS"}],
        [{}],
    )
    merged, using_llm, err = _merge_llm_into_report(base, "这不是 JSON")
    assert using_llm is False
    assert err
    assert "CS2" in merged["executive_summary"]
    assert "```" not in merged["executive_summary"]


@pytest.mark.asyncio
async def test_breakdown_report_rejects_json_pollution(monkeypatch):
    monkeypatch.setattr("src.services.scenario_ai.llm_is_configured", lambda: True)

    async def fake_complete(*_a, **_k):
        return """```json
{"executive_summary":"玩法对比结论","sections":[{"title":"差异","content":"核心循环不同"}]}
```"""

    monkeypatch.setattr("src.services.scenario_ai.complete_prompt", fake_complete)

    from src.services.game_intel import GameLibraryRepository
    from src.services.scenario_ai import generate_breakdown_scenario_report

    gid = GameLibraryRepository.list_games()[0]["game_id"]
    report = await generate_breakdown_scenario_report([gid])
    assert report["success"] is True
    assert report["using_llm"] is True
    assert report["executive_summary"] == "玩法对比结论"
    assert "```json" not in report["executive_summary"]

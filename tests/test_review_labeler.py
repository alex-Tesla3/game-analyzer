"""LLM 评论标签测试(规则回退 + LLM JSON 解析)。"""

from __future__ import annotations

import pytest

from src.services.review_labeler import _extract_json_array, _rule_label, label_review_batch


def test_rule_label_negative():
    label = _rule_label({"content": "这游戏卡顿严重,还有外挂,匹配也烂,退款了"})
    assert label["sentiment"] == "negative"
    assert "performance" in label["topics"]
    assert label["label_source"] == "rule"


def test_rule_label_positive_by_rating():
    label = _rule_label({"content": "game", "rating": 5})
    assert label["sentiment"] == "positive"


def test_extract_json_array():
    raw = '说明文字 [{"index":0,"sentiment":"positive"}] 尾巴'
    assert _extract_json_array(raw) == [{"index": 0, "sentiment": "positive"}]
    assert _extract_json_array("no array") == []


@pytest.mark.asyncio
async def test_label_batch_llm_path(monkeypatch):
    async def fake_complete(prompt, **kwargs):
        return '[{"index":0,"sentiment":"negative","topics":["bugs","performance"],"aspects":{"bugs":"多"},"intent":"complaint","spam_probability":0.2}]'

    import src.services.llm_client as llm
    monkeypatch.setattr(llm, "complete_prompt", fake_complete)

    reviews = [{"review_id": "a", "content": "经常闪退, 掉帧严重"}]
    labels = await label_review_batch(reviews)
    assert labels[0]["review_id"] == "a"
    assert labels[0]["sentiment"] == "negative"
    assert labels[0]["label_source"] == "llm"
    assert "bugs" in labels[0]["topics"]


@pytest.mark.asyncio
async def test_label_batch_rule_fallback(monkeypatch):
    async def fake_complete(prompt, **kwargs):
        raise RuntimeError("LLM down")

    import src.services.llm_client as llm
    monkeypatch.setattr(llm, "complete_prompt", fake_complete)

    reviews = [{"review_id": "a", "content": "画面很好, 手感不错"}]
    labels = await label_review_batch(reviews)
    assert labels[0]["label_source"] == "rule"
    assert labels[0]["sentiment"] == "positive"

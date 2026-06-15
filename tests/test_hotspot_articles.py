"""Tests for industry hotspot deep-dive articles (rule path, no live LLM)."""

from __future__ import annotations

import httpx
import pytest
import pytest_asyncio

from src.services.hotspot_articles import (
    _parse_llm_article,
    _rule_article_markdown,
    _rule_suggest_topic,
    _scale_sample_label,
    build_article_fact_pack,
    create_custom_hotspot_topic,
    delete_custom_hotspot_topic,
    discover_hotspot_topics,
    generate_hotspot_article,
    suggest_hotspot_topic,
)
from src.web_app import app


@pytest_asyncio.fixture
async def api_client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


def test_scale_sample_label():
    assert _scale_sample_label(150_000) == "15万"
    assert _scale_sample_label(25_000) == "2万"
    assert _scale_sample_label(3_500) == "3,500"
    assert _scale_sample_label(42) == "42"


def test_build_article_fact_pack_demo():
    facts = build_article_fact_pack("demo", "730", angle="revenue_decline")
    assert facts["product_id"] == "730"
    assert facts["angle"] == "revenue_decline"
    assert "sample_size" in facts
    assert "sentiment" in facts
    assert "theme_counts" in facts
    assert "data_basis" in facts


def test_discover_hotspot_topics_demo():
    topics = discover_hotspot_topics("demo", limit=6)
    assert topics
    assert all("title" in t and "product_id" in t for t in topics)
    assert any("流水暴跌" in t["title"] or "口碑" in t["title"] for t in topics)


def test_rule_article_markdown_structure():
    facts = build_article_fact_pack("demo", "730", angle="revenue_decline")
    md = _rule_article_markdown(facts)
    assert md.startswith("# ")
    assert "热点背景" in md
    assert "数据说明" in md or "样本" in md
    assert "未配置 LLM" not in md


def test_parse_llm_article_accepts_plain_markdown():
    raw = (
        "# 测试标题\n\n## 一、热点背景\n\n"
        + "这是 AI 直接输出的 Markdown 正文。" * 20
    )
    parsed = _parse_llm_article(raw, {})
    assert parsed is not None
    assert parsed["markdown"].startswith("# 测试标题")


def test_parse_llm_article_extracts_markdown_from_json_blob():
    raw = (
        '{"title":"【深度分析】香肠派对","summary":"样本好评率 78.8%","markdown":'
        '"# 【深度分析】香肠派对\\n\\n## 🚀 热点背景\\n\\n匹配与外挂是核心痛点。"}'
    )
    parsed = _parse_llm_article(raw, {})
    assert parsed is not None
    assert not parsed["markdown"].startswith("{")
    assert "\\n" not in parsed["markdown"]
    assert "## 🚀 热点背景" in parsed["markdown"]
    assert parsed["title"] == "【深度分析】香肠派对"


def test_parse_llm_article_rejects_raw_json_wrapper():
    raw = '{"title":"坏例子","summary":"导语","markdown":"# 只有开头'
    assert _parse_llm_article(raw, {}) is None


@pytest.mark.asyncio
async def test_generate_hotspot_article_rule_based(monkeypatch):
    monkeypatch.setattr("src.services.hotspot_articles.llm_is_configured", lambda: False)
    result = await generate_hotspot_article("demo", product_id="730", angle="revenue_decline")
    assert result["success"] is True
    assert result["using_llm"] is False
    assert result["markdown"].startswith("# ")
    assert result["html"]
    assert "730" == result["product_id"]


@pytest.mark.asyncio
async def test_generate_hotspot_article_custom_brief(monkeypatch):
    monkeypatch.setattr("src.services.hotspot_articles.llm_is_configured", lambda: False)
    brief = "通行证涨价后玩家为何集体差评"
    result = await generate_hotspot_article(
        "demo",
        product_id="730",
        angle="custom",
        custom_brief=brief,
        custom_title=f"《CS2》{brief}？基于样本评论的数据起底",
    )
    assert result["success"] is True
    assert brief in result["markdown"]


def test_rule_suggest_topic_revenue():
    out = _rule_suggest_topic(
        brief="新版本流水暴跌是否与通行证有关",
        product_id="730",
        product_name="CS2",
        sample_label="1万",
    )
    assert out["angle"] == "revenue_decline"
    assert "CS2" in out["title"]


@pytest.mark.asyncio
async def test_suggest_hotspot_topic_rule_based(monkeypatch):
    monkeypatch.setattr("src.services.hotspot_articles.llm_is_configured", lambda: False)
    result = await suggest_hotspot_topic(
        "demo",
        brief="氪金通行证引发口碑危机",
        product_id="730",
    )
    assert result["success"] is True
    assert result["title"]
    assert result["angle"] in ("monetization_backlash", "sentiment_crash", "custom")


def test_custom_hotspot_topic_crud():
    created = create_custom_hotspot_topic(
        "demo",
        product_id="730",
        title="测试自定义热点",
        brief="测试问题描述",
        hook="测试切入点",
        angle="custom",
    )
    assert created["success"] is True
    topic_id = created["topic"]["topic_id"]
    topics = discover_hotspot_topics("demo", limit=30)
    assert any(t.get("topic_id") == topic_id for t in topics)
    deleted = delete_custom_hotspot_topic("demo", topic_id)
    assert deleted["success"] is True


@pytest.mark.asyncio
async def test_hotspot_api_flow(api_client, monkeypatch):
    monkeypatch.setattr("src.services.hotspot_articles.llm_is_configured", lambda: False)
    token = (
        await api_client.post("/token", data={"username": "demo", "password": "demo123"})
    ).json()["access_token"]

    page = await api_client.get("/hotspot")
    assert page.status_code == 200
    assert "行业热点深度分析" in page.text

    topics = await api_client.get("/api/hotspot/topics", params={"token": token})
    assert topics.status_code == 200
    payload = topics.json()
    assert payload["success"] is True
    assert payload["topics"]
    assert payload.get("products")

    suggest = await api_client.post(
        "/api/hotspot/suggest",
        params={"token": token},
        json={"brief": "新版本口碑下滑", "product_id": "730"},
    )
    assert suggest.status_code == 200, suggest.text
    assert suggest.json()["title"]

    custom = await api_client.post(
        "/api/hotspot/custom",
        params={"token": token},
        json={
            "product_id": "730",
            "title": suggest.json()["title"],
            "brief": "新版本口碑下滑",
            "hook": suggest.json().get("hook", ""),
            "angle": suggest.json().get("angle", "custom"),
        },
    )
    assert custom.status_code == 200, custom.text
    topic_id = custom.json()["topic"]["topic_id"]

    first = custom.json()["topic"]
    gen = await api_client.post(
        "/api/hotspot/generate",
        params={"token": token},
        json={"product_id": first["product_id"], "angle": first["angle"]},
    )
    assert gen.status_code == 200, gen.text
    article = gen.json()
    assert article["success"] is True
    assert article["markdown"]

    archived = await api_client.post(
        "/api/hotspot/archive",
        params={"token": token},
        json={
            "title": article["title"],
            "markdown": article["markdown"],
            "html": article["html"],
            "product_id": article["product_id"],
            "angle": article["angle"],
            "facts": article["facts"],
        },
    )
    assert archived.status_code == 200, archived.text
    assert archived.json()["success"] is True
    assert archived.json()["archive_id"]

    deleted = await api_client.delete(
        f"/api/hotspot/custom/{topic_id}",
        params={"token": token},
    )
    assert deleted.status_code == 200
    assert deleted.json()["success"] is True

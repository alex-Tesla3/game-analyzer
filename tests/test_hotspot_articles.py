"""Tests for industry hotspot deep-dive articles (rule path, no live LLM)."""

from __future__ import annotations

import httpx
import pytest
import pytest_asyncio

from src.services.hotspot_articles import (
    _rule_article_markdown,
    _scale_sample_label,
    build_article_fact_pack,
    discover_hotspot_topics,
    generate_hotspot_article,
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

    first = payload["topics"][0]
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

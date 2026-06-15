"""Tests for scenario AI reports (rule-based path, no live LLM)."""

from __future__ import annotations

import httpx
import pytest
import pytest_asyncio

from src.services.game_intel import GameLibraryRepository, seed_default_library
from src.services.scenario_ai import (
    _rule_competitor_report,
    _rule_review_report,
    archive_scenario_report,
    generate_breakdown_scenario_report,
    generate_competitor_scenario_report,
    generate_review_scenario_report,
    get_breakdowns_for_ids,
)
from src.web_app import app


@pytest_asyncio.fixture
async def api_client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest.fixture(autouse=True)
def _seed():
    seed_default_library()


@pytest.mark.asyncio
async def test_competitor_scenario_report_rule_based(monkeypatch):
    monkeypatch.setattr("src.services.scenario_ai.llm_is_configured", lambda: False)
    games = GameLibraryRepository.list_games()
    ids = [g["game_id"] for g in games[:2]]
    report = await generate_competitor_scenario_report(ids, username="demo")
    assert report["success"] is True
    assert report["scenario"] == "competitor"
    assert report["using_llm"] is False
    assert report["executive_summary"]
    assert report["sections"]
    assert report["markdown"].startswith("# ")


@pytest.mark.asyncio
async def test_breakdown_scenario_report_rule_based(monkeypatch):
    monkeypatch.setattr("src.services.scenario_ai.llm_is_configured", lambda: False)
    gid = GameLibraryRepository.list_games()[0]["game_id"]
    report = await generate_breakdown_scenario_report([gid], username="demo")
    assert report["success"] is True
    assert report["scenario"] == "breakdown"
    assert any(g.get("game_id") == gid for g in report["facts"]["games"])


@pytest.mark.asyncio
async def test_review_scenario_report_rule_based(monkeypatch):
    monkeypatch.setattr("src.services.scenario_ai.llm_is_configured", lambda: False)
    report = await generate_review_scenario_report(username="demo")
    assert report["success"] is True
    assert report["scenario"] == "review"
    assert "数据" in report["executive_summary"] or "快照" in report["executive_summary"]


def test_rule_competitor_empty():
    out = _rule_competitor_report({"products": []})
    assert "暂无" in out["executive_summary"]


def test_rule_competitor_single_product():
    out = _rule_competitor_report(
        {
            "products": [
                {
                    "name": "Sausage Man",
                    "positive_rate": 78.33,
                    "risk_level": "medium",
                    "themes": [{"theme": "matchmaking", "count": 5}],
                }
            ]
        }
    )
    assert "相对落后" not in out["executive_summary"]
    assert "单款" in out["executive_summary"] or "单品" in out["title"]
    assert "Sausage Man" in out["executive_summary"]


def test_rule_review_with_deltas():
    out = _rule_review_report(
        deltas=[{"product_name": "CS2", "positive_rate_before": 80, "positive_rate_after": 85, "delta": 5}],
        metrics_summary={"source": "mvp", "product_count": 1, "metrics_rows": 10},
        snapshot_meta={"a": "2026-01-01", "b": "2026-02-01"},
    )
    assert "CS2" in out["executive_summary"]


def test_get_breakdowns_for_ids():
    gid = GameLibraryRepository.list_games()[0]["game_id"]
    payload = get_breakdowns_for_ids([gid])
    assert payload["success"] is True
    assert payload["count"] >= 1
    assert payload["items"][0]["game_id"] == gid


def test_archive_scenario_report_breakdown():
    gid = GameLibraryRepository.list_games()[0]["game_id"]
    report = {
        "success": True,
        "scenario": "breakdown",
        "title": "test",
        "executive_summary": "summary",
        "facts": {"games": [{"game_id": gid, "name": "Test"}]},
        "markdown": "# test",
    }
    archive_id = archive_scenario_report("demo", report)
    assert archive_id


@pytest.mark.asyncio
async def test_scenario_report_api(api_client, monkeypatch):
    monkeypatch.setattr("src.services.scenario_ai.llm_is_configured", lambda: False)
    token = (
        await api_client.post("/token", data={"username": "demo", "password": "demo123"})
    ).json()["access_token"]
    games = GameLibraryRepository.list_games()
    ids = [g["game_id"] for g in games[:2]]

    comp = await api_client.post(
        "/api/scenarios/competitor/report",
        params={"token": token},
        json={"ids": ids},
    )
    assert comp.status_code == 200, comp.text
    assert comp.json()["success"] is True

    bd = await api_client.post(
        "/api/scenarios/breakdown/report",
        params={"token": token},
        json={"game_ids": [ids[0]]},
    )
    assert bd.status_code == 200
    assert bd.json()["scenario"] == "breakdown"

    rev = await api_client.post(
        "/api/scenarios/review/report",
        params={"token": token},
        json={},
    )
    assert rev.status_code == 200
    assert rev.json()["scenario"] == "review"


@pytest.mark.asyncio
async def test_review_page_has_ai_tab(api_client):
    res = await api_client.get("/games/review")
    assert res.status_code == 200
    assert "AI 复盘报告" in res.text
    assert "scenario-report.js" in res.text


@pytest.mark.asyncio
async def test_library_page_has_ai_tab(api_client):
    res = await api_client.get("/games/library")
    assert res.status_code == 200
    assert "AI 总结" in res.text
    assert "scenario-report.js" in res.text

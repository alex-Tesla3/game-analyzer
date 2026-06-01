"""Analysis wizard and actionable report tests."""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from src.services.analysis_wizard import normalize_app_ids, resolve_game_inputs, run_analysis_wizard
from src.services.scenario_ai import build_action_items
from src.web_app import app


from tests.test_mvp_pipeline import FakeSteamCrawler as _FakeCrawler


def test_normalize_app_ids():
    assert normalize_app_ids("730, 570") == ["730", "570"]
    assert normalize_app_ids(["steam_730", "570"]) == ["730", "570"]
    assert normalize_app_ids("bad") == []


def test_resolve_game_inputs_app_id_and_alias():
    out = resolve_game_inputs("cs2, 570")
    assert out["success"] is True
    assert out["app_ids"] == ["730", "570"]
    assert any(r["via"] == "alias" for r in out["resolved"])


def test_resolve_game_inputs_search(monkeypatch):
    monkeypatch.setattr(
        "src.services.analysis_wizard.search_steam_games",
        lambda term, **kw: [{"app_id": "999001", "name": "Test Game Alpha"}]
        if "alpha" in term.lower()
        else [],
    )
    out = resolve_game_inputs("Test Game Alpha")
    assert out["success"] is True
    assert out["app_ids"] == ["999001"]
    assert out["resolved"][0]["via"] == "search"


def test_resolve_game_inputs_not_found(monkeypatch):
    monkeypatch.setattr("src.services.analysis_wizard.search_steam_games", lambda *a, **k: [])
    out = resolve_game_inputs("Unknown Game XYZ")
    assert out["success"] is False
    assert "未找到" in out["message"]


def test_build_action_items_from_mvp():
    facts = {
        "products": [
            {"name": "A", "positive_rate": 45, "themes": [{"theme": "matchmaking"}], "recommendation": "Fix MM"},
            {"name": "B", "positive_rate": 80},
        ],
        "score_summary": [{"name": "A", "average": 2.5}],
    }
    mvp = {
        "ai_strategy": {
            "prioritized_actions": [
                {
                    "priority": 1,
                    "title": "反作弊",
                    "action": "加强举报反馈",
                    "experiment": "cheater 词频下降",
                }
            ]
        }
    }
    items = build_action_items(facts, mvp)
    assert len(items) >= 2
    assert any(i.get("priority") == "P0" for i in items)
    assert any(i.get("source") == "mvp_signals" for i in items)


@pytest_asyncio.fixture
async def api_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest.mark.asyncio
async def test_wizard_run_offline(monkeypatch):
    from src.mvp_pipeline import run_mvp_pipeline

    def fake_pipeline(**kwargs):
        return run_mvp_pipeline(crawler=_FakeCrawler(), app_ids=kwargs.get("app_ids") or ["10"])

    monkeypatch.setattr("src.services.analysis_wizard.run_mvp_pipeline", fake_pipeline)
    monkeypatch.setattr("src.services.scenario_ai.llm_is_configured", lambda: False)

    result = await run_analysis_wizard(["10"], username="demo", auto_archive=False)
    assert result["success"] is True
    assert result["report"]["success"] is True
    assert result.get("action_items")
    assert any(s["id"] == "report" and s["status"] == "ok" for s in result["steps"])


@pytest.mark.asyncio
async def test_wizard_api_and_shared_page(api_client, monkeypatch):
    from src.mvp_pipeline import run_mvp_pipeline

    monkeypatch.setattr(
        "src.services.analysis_wizard.run_mvp_pipeline",
        lambda **kw: run_mvp_pipeline(crawler=_FakeCrawler(), app_ids=kw.get("app_ids") or ["10"]),
    )
    monkeypatch.setattr("src.services.scenario_ai.llm_is_configured", lambda: False)

    token = (
        await api_client.post("/token", data={"username": "demo", "password": "demo123"})
    ).json()["access_token"]

    page = await api_client.get("/guide")
    assert page.status_code == 200
    assert "分析向导" in page.text

    landing = await api_client.get("/")
    assert landing.status_code == 200
    welcome = await api_client.get("/welcome", follow_redirects=False)
    assert welcome.status_code == 307
    dash = await api_client.get("/dashboard")
    assert dash.status_code == 200

    res = await api_client.post(
        "/api/wizard/run",
        params={"token": token},
        json={"app_ids": "10", "auto_archive": False},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    assert body["report"].get("action_items")

    shared_page = await api_client.get("/shared/test-token-404")
    assert shared_page.status_code == 200

"""Tests for core module extensions: versions, scores, archives."""

from __future__ import annotations

import httpx
import pytest
import pytest_asyncio

from src.services.analysis_archive import AnalysisArchiveRepository, ARCHIVE_CATEGORIES
from src.services.competitor_scores import (
    CompetitorScoreRepository,
    build_score_summary,
    normalize_scores,
    suggest_scores_from_item,
)
from src.services.game_intel import GameLibraryRepository, seed_default_library
from src.services.game_versions import GameVersionRepository
from src.web_app import app


@pytest_asyncio.fixture
async def api_client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest.fixture(autouse=True)
def _seed():
    seed_default_library()


@pytest.fixture
def token(api_client):
    async def _get():
        r = await api_client.post("/token", data={"username": "demo", "password": "demo123"})
        return r.json()["access_token"]
    return _get


def test_normalize_scores_clamps():
    assert normalize_scores({"gameplay": 6, "ux": 0, "social": 3}) == {"gameplay": 5, "social": 3, "ux": 1}


def test_suggest_scores_from_item():
    scores = suggest_scores_from_item({"positive_rate": 80, "risk_level": "low"})
    assert 1 <= scores["gameplay"] <= 5


def test_game_version_crud():
    gid = GameLibraryRepository.list_games()[0]["game_id"]
    vid = GameVersionRepository.create(gid, {"version_label": "v1.0", "change_summary": "首发"})
    versions = GameVersionRepository.list_for_game(gid)
    assert any(v["version_id"] == vid for v in versions)
    GameVersionRepository.delete(vid)


def test_competitor_score_upsert():
    gid = GameLibraryRepository.list_games()[0]["game_id"]
    saved = CompetitorScoreRepository.upsert("demo", gid, {"gameplay": 4, "ux": 5})
    assert saved["gameplay"] == 4
    assert CompetitorScoreRepository.get("demo", gid)["ux"] == 5


def test_build_score_summary():
    rows = [
        {"game_id": "a", "name": "A", "scores": {"gameplay": 5, "ux": 3}},
        {"game_id": "b", "name": "B", "scores": {"gameplay": 3, "ux": 3}},
    ]
    ranked = build_score_summary(rows)
    assert ranked[0]["name"] == "A"


def test_archive_update_with_category():
    aid = AnalysisArchiveRepository.create(
        username="demo",
        title="测试报告",
        report_type="ai_competitor",
        product_ids=["730"],
        body_markdown="# 初稿",
        category="竞品分析",
        tags=["test"],
    )
    AnalysisArchiveRepository.update(aid, "demo", {"title": "更新标题", "body_markdown": "# 已编辑"})
    row = AnalysisArchiveRepository.get(aid, "demo")
    assert row["title"] == "更新标题"
    assert "已编辑" in row["body_markdown"]
    assert row["category"] == "竞品分析"


@pytest.mark.asyncio
async def test_compare_includes_dimension_scores(api_client):
    token = (
        await api_client.post("/token", data={"username": "demo", "password": "demo123"})
    ).json()["access_token"]
    games = GameLibraryRepository.list_games()
    ids = ",".join(g["game_id"] for g in games[:2])
    res = await api_client.get("/api/games/compare", params={"token": token, "ids": ids})
    body = res.json()
    assert body["success"] is True
    assert "dimension_scores" in body
    assert body["dimension_scores"]["rows"]
    assert "score_summary" in body


@pytest.mark.asyncio
async def test_version_api(api_client):
    token = (
        await api_client.post("/token", data={"username": "demo", "password": "demo123"})
    ).json()["access_token"]
    gid = GameLibraryRepository.list_games()[0]["game_id"]
    create = await api_client.post(
        f"/api/games/library/{gid}/versions",
        params={"token": token},
        json={"version_label": "v2.0", "change_summary": "大更新"},
    )
    assert create.status_code == 200
    listing = await api_client.get(f"/api/games/library/{gid}/versions", params={"token": token})
    assert listing.json()["success"] is True
    assert listing.json()["versions"]


@pytest.mark.asyncio
async def test_archive_edit_api(api_client):
    token = (
        await api_client.post("/token", data={"username": "demo", "password": "demo123"})
    ).json()["access_token"]
    aid = AnalysisArchiveRepository.create(
        username="demo",
        title="API 测试",
        report_type="test",
        product_ids=[],
        body_markdown="old",
    )
    res = await api_client.put(
        f"/api/games/archives/{aid}",
        params={"token": token},
        json={"title": "新标题", "body_markdown": "new body", "category": "其他", "tags": ["a"]},
    )
    assert res.status_code == 200
    got = await api_client.get(f"/api/games/archives/{aid}", params={"token": token})
    assert got.json()["archive"]["title"] == "新标题"


def test_archive_categories_defined():
    assert "竞品分析" in ARCHIVE_CATEGORIES

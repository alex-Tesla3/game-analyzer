"""Tests for competitor workbench, archives, and framework routes."""

from __future__ import annotations

import httpx
import pytest
import pytest_asyncio

from src.services.competitor_workbench import build_feature_matrix
from src.services.game_genre import assign_competitors_by_genre, infer_product_genre
from src.services.game_intel import GameLibraryRepository, seed_default_library
from src.web_app import app


@pytest_asyncio.fixture
async def api_client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest.fixture(autouse=True)
def _seed():
    seed_default_library()


def test_infer_product_genre_steam_ids():
    assert infer_product_genre("730", "Counter-Strike 2") == "FPS"
    assert infer_product_genre("570", "Dota 2") == "MOBA"


def test_assign_competitors_by_genre_same_genre():
    products = {
        "730": {"name": "CS2", "genre": "FPS"},
        "1172470": {"name": "Apex", "genre": "FPS"},
        "570": {"name": "Dota", "genre": "MOBA"},
    }
    mapping = assign_competitors_by_genre(products)
    fps_peers = mapping["steam_730"]
    assert "steam_1172470" in fps_peers
    assert "steam_570" not in fps_peers


def test_assign_competitors_solo_genre_uses_related():
    """ELDEN RING is the only RPG in MVP batch — should still get Open World peers."""
    products = {
        "1245620": {"name": "ELDEN RING", "genre": "RPG"},
        "1091500": {"name": "Cyberpunk 2077", "genre": "Open World"},
        "730": {"name": "CS2", "genre": "FPS"},
    }
    mapping = assign_competitors_by_genre(products)
    elden_peers = mapping["steam_1245620"]
    assert "steam_1091500" in elden_peers
    assert "steam_1245620" not in elden_peers


def test_assign_competitors_mvp_batch_elden_not_empty():
    from src.mvp_pipeline import DEFAULT_STEAM_APP_IDS

    products = {
        pid: {"name": pid, "genre": infer_product_genre(pid, "")}
        for pid in DEFAULT_STEAM_APP_IDS
    }
    mapping = assign_competitors_by_genre(products)
    assert mapping["steam_1245620"]
    assert len(mapping["steam_1245620"]) >= 1


def test_build_feature_matrix_seed_games():
    from src.services.game_intel import GameplayBreakdownRepository, _template_breakdown_for_genre

    gid_a = GameLibraryRepository.create(
        {"name": "Matrix Test A", "genre": "FPS", "platforms": ["PC"]}
    )
    gid_b = GameLibraryRepository.create(
        {"name": "Matrix Test B", "genre": "MOBA", "platforms": ["PC"]}
    )
    GameplayBreakdownRepository.upsert(
        gid_a, _template_breakdown_for_genre("FPS", "Matrix Test A")
    )
    GameplayBreakdownRepository.upsert(
        gid_b, _template_breakdown_for_genre("MOBA", "Matrix Test B")
    )
    matrix = build_feature_matrix([gid_a, gid_b])
    assert matrix["success"] is True
    assert len(matrix["rows"]) == 2
    assert matrix["sections"]


@pytest.mark.asyncio
async def test_compare_page(api_client):
    compare = await api_client.get("/games/compare")
    assert compare.status_code == 200
    assert "竞品分析" in compare.text
    assert "AI 总结" in compare.text


@pytest.mark.asyncio
async def test_review_page(api_client):
    response = await api_client.get("/games/review")
    assert response.status_code == 200
    assert "复盘与归档" in response.text
    assert "分析案例归档" in response.text


@pytest.mark.asyncio
async def test_framework_redirects_home(api_client):
    response = await api_client.get("/framework", follow_redirects=False)
    assert response.status_code == 200
    assert "analysis-guide" in response.text or "分析指引" in response.text


@pytest.mark.asyncio
async def test_compare_api(api_client):
    token = (
        await api_client.post("/token", data={"username": "demo", "password": "demo123"})
    ).json()["access_token"]
    games = (await api_client.get("/api/games/library", params={"token": token})).json()["games"]
    ids = ",".join(g["game_id"] for g in games[:2])
    res = await api_client.get("/api/games/compare", params={"token": token, "ids": ids})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["success"] is True
    assert len(body["items"]) >= 1
    assert "feature_matrix" in body


@pytest.mark.asyncio
async def test_data_provenance_api(api_client):
    token = (
        await api_client.post("/token", data={"username": "demo", "password": "demo123"})
    ).json()["access_token"]
    res = await api_client.get("/api/data/provenance", params={"token": token})
    assert res.status_code == 200
    body = res.json()
    assert "source" in body
    assert body["trust"]["label"]


@pytest.mark.asyncio
async def test_options_includes_genres(api_client):
    token = (
        await api_client.post("/token", data={"username": "demo", "password": "demo123"})
    ).json()["access_token"]
    res = await api_client.get("/api/options", params={"token": token})
    assert res.status_code == 200
    body = res.json()
    assert "genres" in body
    assert "data_source" in body


@pytest.mark.asyncio
async def test_archives_list(api_client):
    token = (
        await api_client.post("/token", data={"username": "demo", "password": "demo123"})
    ).json()["access_token"]
    res = await api_client.get("/api/games/archives", params={"token": token})
    assert res.status_code == 200
    assert res.json()["success"] is True

"""Tests for game library and gameplay breakdown module."""

from __future__ import annotations

import httpx
import pytest
import pytest_asyncio

from src.services.game_intel import GameLibraryRepository, seed_default_library
from src.web_app import app


@pytest_asyncio.fixture
async def api_client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest.fixture(autouse=True)
def _ensure_seed():
    seed_default_library()


@pytest.mark.asyncio
async def test_library_page_loads(api_client):
    response = await api_client.get("/games/library")
    assert response.status_code == 200
    assert "游戏资料库" in response.text


@pytest.mark.asyncio
async def test_list_and_detail_library(api_client):
    token = (
        await api_client.post("/token", data={"username": "demo", "password": "demo123"})
    ).json()["access_token"]

    listing = await api_client.get("/api/games/library", params={"token": token})
    assert listing.status_code == 200, listing.text
    games = listing.json()["games"]
    assert len(games) >= 3

    game_id = games[0]["game_id"]
    detail = await api_client.get(f"/api/games/library/{game_id}", params={"token": token})
    assert detail.status_code == 200, detail.text
    body = detail.json()
    assert body["success"] is True
    assert body["game"]["game_id"] == game_id
    assert "sections" in body
    assert (body["breakdown"].get("core_loop") or "").strip()


@pytest.mark.asyncio
async def test_save_breakdown(api_client):
    token = (
        await api_client.post("/token", data={"username": "demo", "password": "demo123"})
    ).json()["access_token"]
    games = (await api_client.get("/api/games/library", params={"token": token})).json()["games"]
    game_id = games[0]["game_id"]

    save = await api_client.put(
        f"/api/games/library/{game_id}/breakdown",
        params={"token": token},
        json={"core_loop": "测试核心循环", "auto_generated": False},
    )
    assert save.status_code == 200, save.text

    detail = await api_client.get(f"/api/games/library/{game_id}", params={"token": token})
    assert "测试核心循环" in detail.json()["breakdown"]["core_loop"]


@pytest.mark.asyncio
async def test_create_game(api_client):
    token = (
        await api_client.post("/token", data={"username": "demo", "password": "demo123"})
    ).json()["access_token"]
    response = await api_client.post(
        "/api/games/library",
        params={"token": token},
        json={"name": "测试竞品游戏", "genre": "FPS", "platforms": ["PC"]},
    )
    assert response.status_code == 200, response.text
    game_id = response.json()["game_id"]
    assert GameLibraryRepository.get(game_id)


@pytest.mark.asyncio
async def test_delete_game(api_client):
    token = (
        await api_client.post("/token", data={"username": "demo", "password": "demo123"})
    ).json()["access_token"]
    create = await api_client.post(
        "/api/games/library",
        params={"token": token},
        json={"name": "待删除游戏", "genre": "FPS", "platforms": ["PC"]},
    )
    game_id = create.json()["game_id"]
    assert GameLibraryRepository.get(game_id)

    delete = await api_client.delete(
        f"/api/games/library/{game_id}",
        params={"token": token},
    )
    assert delete.status_code == 200, delete.text
    assert delete.json()["success"] is True
    assert GameLibraryRepository.get(game_id) is None

    missing = await api_client.get(f"/api/games/library/{game_id}", params={"token": token})
    assert missing.status_code == 404

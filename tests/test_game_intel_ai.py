"""Tests for AI gameplay breakdown generation."""

from __future__ import annotations

import json

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


async def _token(client):
    response = await client.post("/token", data={"username": "demo", "password": "demo123"})
    return response.json()["access_token"]


@pytest.mark.asyncio
async def test_library_meta_includes_llm_flag(api_client):
    token = await _token(api_client)
    response = await api_client.get("/api/games/library/meta", params={"token": token})
    assert response.status_code == 200
    body = response.json()
    assert "llm_configured" in body


@pytest.mark.asyncio
async def test_ai_generate_fallback_without_llm(api_client, monkeypatch):
    from src.services import game_intel_ai

    monkeypatch.setattr(game_intel_ai, "llm_is_configured", lambda: False)

    token = await _token(api_client)
    games = (await api_client.get("/api/games/library", params={"token": token})).json()["games"]
    game_id = games[0]["game_id"]

    response = await api_client.post(
        f"/api/games/library/{game_id}/breakdown/generate-ai",
        params={"token": token},
        json={"refine": False, "save": True},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True
    assert body["using_llm"] is False
    assert body["breakdown"].get("core_loop")

    detail = await api_client.get(f"/api/games/library/{game_id}", params={"token": token})
    assert detail.json()["breakdown"].get("core_loop")


@pytest.mark.asyncio
async def test_ai_generate_with_mock_llm(api_client, monkeypatch):
    from src.services import game_intel_ai

    monkeypatch.setattr(game_intel_ai, "llm_is_configured", lambda: True)

    async def fake_complete(prompt: str, *, max_tokens: int = 500):
        assert "核心循环" in prompt or "core_loop" in prompt
        return json.dumps(
            {
                "core_loop": "AI：选英雄对线团战推塔",
                "progression": "AI：段位与皮肤",
                "monetization": "AI：皮肤与通行证",
                "social_features": "AI：开黑排位",
                "session_design": "AI：单局20分钟",
                "differentiation": "AI：英雄差异化",
                "benchmarks": "AI：参考王者荣耀",
                "analysis_notes": "AI测试生成",
            },
            ensure_ascii=False,
        )

    monkeypatch.setattr(game_intel_ai, "complete_prompt", fake_complete)

    token = await _token(api_client)
    game_id = GameLibraryRepository.create(
        {"name": "AI测试游戏", "genre": "MOBA", "platforms": ["PC"], "tags": []}
    )

    response = await api_client.post(
        f"/api/games/library/{game_id}/breakdown/generate-ai",
        params={"token": token},
        json={"save": True},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True
    assert body["using_llm"] is True
    assert "AI：选英雄" in body["breakdown"]["core_loop"]


@pytest.mark.asyncio
async def test_ai_refine_requires_content(api_client, monkeypatch):
    from src.services import game_intel_ai

    monkeypatch.setattr(game_intel_ai, "llm_is_configured", lambda: True)

    token = await _token(api_client)
    game_id = GameLibraryRepository.create(
        {"name": "空拆解游戏", "genre": "FPS", "platforms": ["PC"], "tags": []}
    )

    response = await api_client.post(
        f"/api/games/library/{game_id}/breakdown/generate-ai",
        params={"token": token},
        json={"refine": True, "current_breakdown": {}},
    )
    assert response.status_code == 200
    assert response.json()["success"] is False

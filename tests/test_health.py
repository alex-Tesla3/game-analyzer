"""Health endpoint contract tests."""

from __future__ import annotations

import httpx
import pytest
import pytest_asyncio

from src.web_app import app


@pytest_asyncio.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_health_returns_version_and_environment(client):
    response = await client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "game_analyzer"
    assert "version" in body
    assert "environment" in body
    assert "demo_accounts_enabled" in body
    assert "timestamp" in body

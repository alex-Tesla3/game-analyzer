"""Tests for commercial work-guidance summary."""

from __future__ import annotations

import httpx
import pytest
import pytest_asyncio

from src.services.work_guidance import work_guidance_summary


@pytest_asyncio.fixture
async def api_client():
    from src.web_app import app

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


async def _token(client: httpx.AsyncClient) -> str:
    res = await client.post("/token", data={"username": "demo", "password": "demo123"})
    return res.json()["access_token"]


@pytest.mark.asyncio
async def test_work_guidance_empty(api_client):
    token = await _token(api_client)
    res = await api_client.get(f"/api/work/guidance?token={token}")
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["progress_pct"] >= 0
    assert len(data["steps"]) == 4


@pytest.mark.asyncio
async def test_api_user_includes_usage(api_client):
    token = await _token(api_client)
    res = await api_client.get(f"/api/user?token={token}")
    assert res.status_code == 200
    user = res.json()
    assert "api_usage" in user
    assert "api_remaining" in user
    assert "api_quota_monthly" in user


@pytest.mark.asyncio
async def test_review_redirect(api_client):
    res = await api_client.get("/review", follow_redirects=False)
    assert res.status_code == 307
    assert res.headers["location"] == "/games/review"


@pytest.mark.asyncio
async def test_team_page(api_client):
    res = await api_client.get("/team")
    assert res.status_code == 200
    assert "团队协作" in res.text


@pytest.mark.asyncio
async def test_work_page(api_client):
    res = await api_client.get("/work")
    assert res.status_code == 200
    assert "落地指导" in res.text


def test_work_guidance_summary_steps():
    data = work_guidance_summary("__nonexistent_user__")
    assert data["success"] is True
    assert all(s["id"] in ("analyze", "export", "share", "retest") for s in data["steps"])
    assert data["steps"][0]["done"] is False

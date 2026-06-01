"""Team API integration tests."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from src.web_app import app


@pytest.fixture
async def api_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


async def _token(client: AsyncClient) -> str:
    res = await client.post("/token", data={"username": "demo", "password": "demo123"})
    return res.json()["access_token"]


@pytest.mark.asyncio
async def test_create_team_lists_members_and_archives(api_client):
    token = await _token(api_client)

    create = await api_client.post(
        f"/api/teams?token={token}",
        json={"name": "集成测试团队"},
    )
    body = create.json()
    assert body.get("success") is True
    team_id = body["team_id"]

    teams = await api_client.get(f"/api/teams?token={token}")
    teams_body = teams.json()
    assert teams_body.get("success") is True
    assert any(t.get("name") == "集成测试团队" and "id" in t for t in teams_body.get("teams", []))

    members = await api_client.get(f"/api/teams/{team_id}/members?token={token}")
    assert members.status_code == 200
    members_body = members.json()
    assert members_body.get("success") is True
    assert members_body["members"][0]["username"] == "demo"
    assert members_body["members"][0]["role"] == "admin"

    archives = await api_client.get(f"/api/teams/{team_id}/archives?token={token}")
    assert archives.status_code == 200
    archives_body = archives.json()
    assert archives_body.get("success") is True
    assert isinstance(archives_body.get("archives"), list)

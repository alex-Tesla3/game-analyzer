"""Agent API 测试(离线)。"""

from __future__ import annotations

import json
import uuid

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from src.web_app import app

    return TestClient(app)


def _register_and_token(client: TestClient) -> str:
    username = f"agent_{uuid.uuid4().hex[:8]}"
    password = "agent-test-pass"
    client.post(
        "/register",
        data={"username": username, "email": f"{username}@example.com", "password": password},
        headers={"X-Device-Id": f"device-{username}"},
    )
    res = client.post(
        "/token",
        data={"username": username, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


def test_agent_status(client, monkeypatch):
    monkeypatch.delenv("SUPABASE_DATABASE_URL", raising=False)
    token = _register_and_token(client)
    res = client.get("/api/agent/status", params={"token": token})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["success"] is True
    assert body["supabase_enabled"] is False
    assert "clean" in body["steps"]


def test_agent_process_offline(client, tmp_path, monkeypatch):
    monkeypatch.delenv("SUPABASE_DATABASE_URL", raising=False)
    token = _register_and_token(client)

    data = {
        "source": "test",
        "games": [{"app_id": "10", "name": "Counter-Strike"}],
        "comments": [
            {"product": "10", "platform": "Steam", "内容": "Great team game."},
            {"product": "10", "platform": "Steam", "内容": "Great team game."},
            {"product": "10", "platform": "Steam", "内容": "画面很好,手感不错,强烈推荐"},
        ],
        "metrics": [],
    }
    path = tmp_path / "steam_dataset.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    res = client.post(
        "/api/agent/process",
        params={"token": token},
        json={"dataset_path": str(path), "steps": ["clean", "label", "aggregate"], "use_llm": False},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["success"] is True
    assert body["aggregate"]["clean_reviews"] == 1

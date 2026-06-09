"""Ollama connection helpers and admin test endpoint."""

from __future__ import annotations

from unittest.mock import MagicMock

import httpx
import pytest
import pytest_asyncio

from src.services.llm_client import _ollama_base_url, _ollama_error_message
from src.web_app import app


@pytest_asyncio.fixture
async def api_client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


def test_ollama_base_url_strips_api_suffixes():
    assert _ollama_base_url("http://localhost:11434/api/generate") == "http://localhost:11434"
    assert _ollama_base_url("http://localhost:11434/api") == "http://localhost:11434"
    assert _ollama_base_url("http://localhost:11434/api/chat") == "http://localhost:11434"


def test_ollama_error_message_model_not_found():
    resp = MagicMock()
    resp.status_code = 404
    resp.json.return_value = {"error": "model 'llama3.2' not found"}
    msg = _ollama_error_message(resp, "llama3.2", "http://localhost:11434")
    assert "llama3.2" in msg
    assert "未在本机" in msg or "未安装" in msg


@pytest.mark.asyncio
async def test_llm_test_rejects_missing_ollama_model(api_client, monkeypatch):
    async def fake_models(_endpoint=None):
        return ["gemma4:latest"]

    monkeypatch.setattr("src.routers.llm_router.get_local_ollama_models", fake_models)

    login = await api_client.post("/token", data={"username": "admin", "password": "admin123"})
    token = login.json()["access_token"]

    res = await api_client.post(
        f"/api/llm/test?token={token}",
        json={"provider": "ollama", "model": "llama3.2", "endpoint": "http://localhost:11434"},
    )
    body = res.json()
    assert body["success"] is False
    assert "llama3.2" in body["message"]
    assert "gemma4:latest" in body["message"]

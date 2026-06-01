"""Tests for action tasks and retest loop."""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from src.services.action_tasks import (
    actions_to_csv,
    apply_action_status_updates,
    normalize_action_items,
)
from src.services.retest_loop import compute_product_deltas, verify_action_items
from src.web_app import app


def test_normalize_action_items_defaults():
    items = normalize_action_items([{"title": "Fix MM", "priority": "P0"}])
    assert items[0]["status"] == "pending"
    assert items[0]["id"] == "0"


def test_actions_to_csv_contains_header():
    csv_text = actions_to_csv([{"priority": "P0", "title": "Test", "action": "Do it"}])
    assert "priority" in csv_text
    assert "P0" in csv_text


def test_apply_action_status_updates():
    items = normalize_action_items([{"title": "A"}, {"title": "B"}])
    updated = apply_action_status_updates(items, {"0": {"status": "done"}})
    assert updated[0]["status"] == "done"
    assert updated[1]["status"] == "pending"


def test_compute_product_deltas():
    before = {"730": {"product": "730", "name": "CS2", "positive_rate": 70}}
    after = {"730": {"product": "730", "name": "CS2", "positive_rate": 72}}
    deltas = compute_product_deltas(before, after)
    assert len(deltas) == 1
    assert deltas[0]["delta"] == 2.0


def test_verify_action_items_p0_improved():
    items = [
        {
            "priority": "P0",
            "source": "compare",
            "title": "Fix laggard",
            "status": "pending",
        }
    ]
    deltas = [
        {
            "product": "730",
            "product_name": "CS2",
            "positive_rate_before": 50,
            "positive_rate_after": 52,
            "delta": 2.0,
        }
    ]
    out = verify_action_items(items, deltas)
    assert out[0]["status"] == "verified"


@pytest_asyncio.fixture
async def api_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest.mark.asyncio
async def test_wizard_export_actions_csv(api_client):
    token = (
        await api_client.post("/token", data={"username": "demo", "password": "demo123"})
    ).json()["access_token"]
    res = await api_client.post(
        "/api/wizard/export/actions",
        params={"token": token, "format": "csv"},
        json={"action_items": [{"priority": "P1", "title": "Expand sample", "action": "crawl"}]},
    )
    assert res.status_code == 200
    assert "priority" in res.text


@pytest.mark.asyncio
async def test_retest_archive_offline(api_client, monkeypatch):
    from src.mvp_pipeline import run_mvp_pipeline
    from tests.test_mvp_pipeline import FakeSteamCrawler

    monkeypatch.setattr(
        "src.services.analysis_wizard.run_mvp_pipeline",
        lambda **kw: run_mvp_pipeline(crawler=FakeSteamCrawler(), app_ids=kw.get("app_ids") or ["10"]),
    )
    monkeypatch.setattr("src.services.scenario_ai.llm_is_configured", lambda: False)

    token = (
        await api_client.post("/token", data={"username": "demo", "password": "demo123"})
    ).json()["access_token"]

    wizard = await api_client.post(
        "/api/wizard/run",
        params={"token": token},
        json={"app_ids": "10", "auto_archive": True},
    )
    assert wizard.status_code == 200
    archive_id = wizard.json().get("archive_id")
    assert archive_id

    retest = await api_client.post(
        f"/api/games/archives/{archive_id}/retest",
        params={"token": token},
        json={},
    )
    assert retest.status_code == 200
    body = retest.json()
    assert body.get("success") is True
    assert body.get("deltas") is not None

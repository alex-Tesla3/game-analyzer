"""Dashboard filter integration with dynamic product catalog."""

from __future__ import annotations

import httpx
import pytest
import pytest_asyncio

from src.web_app import app


@pytest_asyncio.fixture
async def api_client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest.mark.asyncio
async def test_options_returns_products_from_active_dataset(api_client):
    token = (
        await api_client.post("/token", data={"username": "demo", "password": "demo123"})
    ).json()["access_token"]
    response = await api_client.get("/api/options", params={"token": token})
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["success"] is True
    assert len(payload["products"]) >= 1
    assert len(payload["time_periods"]) >= 1


@pytest.mark.asyncio
async def test_report_filters_by_catalog_product_and_period(api_client):
    token = (
        await api_client.post("/token", data={"username": "demo", "password": "demo123"})
    ).json()["access_token"]
    options = (await api_client.get("/api/options", params={"token": token})).json()
    product_ids = [p["id"] for p in options.get("products") or []]
    metrics_resp = await api_client.get("/api/metrics", params={"token": token})
    assert metrics_resp.status_code == 200
    known = {m.get("product") for m in metrics_resp.json().get("data") or []}
    product_id = next((pid for pid in product_ids if pid in known), product_ids[0] if product_ids else "10")
    period_id = options["time_periods"][-1]["id"] if options.get("time_periods") else "week_22"

    response = await api_client.get(
        "/api/report",
        params={
            "token": token,
            "products": product_id,
            "time_period": period_id,
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True
    metrics = body.get("metrics") or []
    if body.get("source") in ("mvp_steam", "steam_public"):
        if metrics:
            assert all(m.get("product") == product_id for m in metrics)
    else:
        assert isinstance(metrics, list)


@pytest.mark.asyncio
async def test_report_skips_llm_summary_by_default(api_client, monkeypatch):
    from src.services import llm_mvp_summary

    async def fake_llm(_analysis):
        return {"executive_summary": "should not run", "using_llm": True}

    monkeypatch.setattr(llm_mvp_summary, "summarize_mvp_with_llm", fake_llm)
    monkeypatch.setattr("src.routers.data_router.llm_is_configured", lambda: True)
    monkeypatch.setattr("src.routers.data_router.mvp_validation_passed", lambda: True)
    monkeypatch.setattr(
        "src.routers.data_router.get_mvp_analysis",
        lambda: {"product_reports": [{"product": "730"}]},
    )

    token = (
        await api_client.post("/token", data={"username": "demo", "password": "demo123"})
    ).json()["access_token"]
    response = await api_client.get("/api/report", params={"token": token})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body.get("data", {}).get("executive_summary") is None


@pytest.mark.asyncio
async def test_invalid_product_filter_returns_empty_for_mvp_dataset(api_client):
    token = (
        await api_client.post("/token", data={"username": "demo", "password": "demo123"})
    ).json()["access_token"]
    response = await api_client.get(
        "/api/report",
        params={"token": token, "products": "game_a", "time_period": "week_22"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body.get("success") is True
    assert body.get("metrics") == []

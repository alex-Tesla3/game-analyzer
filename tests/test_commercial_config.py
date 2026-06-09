"""Commercial deployment profile and payment mode."""

from __future__ import annotations

import pytest

from src.commercial_config import (
    commercial_status_payload,
    payment_mode,
    production_startup_warnings,
)


@pytest.mark.parametrize(
    "env,test_mode,secret,expected",
    [
        ("development", None, "", "demo"),
        ("production", "true", "", "demo"),
        ("production", "false", "sec", "webhook"),
        ("production", "false", "", "blocked"),
    ],
)
def test_payment_mode(monkeypatch, env, test_mode, secret, expected):
    monkeypatch.setenv("APP_ENV", env)
    if test_mode is not None:
        monkeypatch.setenv("PAYMENT_TEST_MODE", test_mode)
    else:
        monkeypatch.delenv("PAYMENT_TEST_MODE", raising=False)
    monkeypatch.setenv("PAYMENT_WEBHOOK_SECRET", secret)
    assert payment_mode() == expected


def test_commercial_status_payload_shape(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    payload = commercial_status_payload()
    assert payload["payment_mode"] == "demo"
    assert payload["data_trust_path"] == "/trust"
    assert "deploy_profile_label" in payload


def test_production_warnings_demo_accounts(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("ALLOW_DEMO_ACCOUNTS", "true")
    monkeypatch.setenv("PAYMENT_TEST_MODE", "true")
    monkeypatch.setenv("SECRET_KEY", "real-secret")
    warnings = production_startup_warnings()
    assert any("ALLOW_DEMO_ACCOUNTS" in w for w in warnings)
    assert any("PAYMENT_TEST_MODE" in w for w in warnings)


def test_commercial_status_api_route():
    from fastapi.testclient import TestClient

    from src.web_app import app

    client = TestClient(app)
    res = client.get("/api/commercial/status")
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    assert body["payment_mode"] in ("demo", "webhook", "blocked")


def test_trust_page_route():
    from fastapi.testclient import TestClient

    from src.web_app import app

    client = TestClient(app)
    res = client.get("/trust")
    assert res.status_code == 200
    assert "数据与订阅说明" in res.text

"""Stripe checkout webhook (mocked — no live Stripe API)."""

from __future__ import annotations

import json
import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from src.web_app import app

    return TestClient(app)


def _register_and_token(client: TestClient) -> str:
    username = f"stripe_{uuid.uuid4().hex[:8]}"
    password = "stripe-test-pass"
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


def test_stripe_webhook_marks_order_paid(client, monkeypatch):
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test")
    monkeypatch.setenv("PAYMENT_TEST_MODE", "false")
    monkeypatch.setenv("APP_ENV", "production")

    token = _register_and_token(client)
    with patch("src.services.stripe_orders.stripe_webhook_configured", return_value=True):
        order_res = client.post(
            "/api/payment/create-order",
            params={"token": token},
            json={"plan_id": "pro", "payment_method": "wechat"},
        )
    assert order_res.status_code == 200, order_res.text
    order_id = order_res.json()["order_id"]

    fake_event = MagicMock()
    fake_event.type = "checkout.session.completed"
    fake_event.data.object.id = "cs_test_123"
    fake_event.data.object.metadata = {"order_id": order_id}

    with patch(
        "src.routers.payment_router.construct_webhook_event",
        return_value=fake_event,
    ):
        with patch("src.routers.payment_router.stripe_webhook_configured", return_value=True):
            wh = client.post(
                "/api/payment/webhook/stripe",
                content=b"{}",
                headers={"Stripe-Signature": "test_sig"},
            )
    assert wh.status_code == 200, wh.text
    assert wh.json()["success"] is True

    order = client.get(f"/api/payment/order/{order_id}", params={"token": token}).json()
    assert order["order"]["payment_status"] == "paid"


def test_commercial_status_includes_stripe_flag(client, monkeypatch):
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    res = client.get("/api/commercial/status")
    body = res.json()
    assert "stripe_checkout_available" in body

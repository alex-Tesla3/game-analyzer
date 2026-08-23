"""Waffo payment integration tests (mocked HTTP — no live Waffo API)."""

from __future__ import annotations

import base64
import json
import uuid
from unittest.mock import patch

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from fastapi.testclient import TestClient


def _keypair():
    """Generate an RSA keypair; base64 DER like the Waffo SDK expects."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_der = private_key.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_der = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return (
        base64.b64encode(private_der).decode("ascii"),
        base64.b64encode(public_der).decode("ascii"),
    )


PRIVATE_KEY, PUBLIC_KEY = _keypair()


def _sign(body: str) -> str:
    key = serialization.load_der_private_key(base64.b64decode(PRIVATE_KEY), password=None)
    sig = key.sign(body.encode("utf-8"), padding.PKCS1v15(), hashes.SHA256())
    return base64.b64encode(sig).decode("ascii")


@pytest.fixture
def client():
    from src.web_app import app

    return TestClient(app)


@pytest.fixture
def waffo_env(monkeypatch):
    monkeypatch.setenv("WAFFO_API_KEY", "waffo_api_key_test")
    monkeypatch.setenv("WAFFO_PRIVATE_KEY", PRIVATE_KEY)
    monkeypatch.setenv("WAFFO_PUBLIC_KEY", PUBLIC_KEY)
    monkeypatch.setenv("WAFFO_MERCHANT_ID", "1000000201")
    monkeypatch.setenv("WAFFO_ENV", "sandbox")
    monkeypatch.setenv("WAFFO_ORDER_CURRENCY", "CNY")


def _clear_pancake_env(monkeypatch):
    for name in (
        "WAFFO_PANCAKE_MERCHANT_ID",
        "WAFFO_PANCAKE_STORE_ID",
        "WAFFO_PANCAKE_PRIVATE_KEY",
        "WAFFO_PANCAKE_PRODUCT_ID",
        "WAFFO_PANCAKE_PRODUCT_IDS",
        "WAFFO_PANCAKE_ENV",
        "WAFFO_PANCAKE_WEBHOOK_PUBLIC_KEY",
    ):
        monkeypatch.delenv(name, raising=False)


def _register_and_token(client: TestClient) -> str:
    username = f"waffo_{uuid.uuid4().hex[:8]}"
    password = "waffo-test-pass"
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


# ---------------------------------------------------------------------------
# Unit: signing
# ---------------------------------------------------------------------------

def test_sign_verify_roundtrip(waffo_env):
    from src.services import waffo_payment

    body = '{"merchantOrderId":"ORD123"}'
    signature = waffo_payment.sign(body)
    assert waffo_payment.verify_signature(body, signature) is True
    assert waffo_payment.verify_signature(body + " ", signature) is False
    assert waffo_payment.verify_signature(body, "bad-signature") is False


def test_waffo_configured(waffo_env):
    from src.services import waffo_payment

    assert waffo_payment.waffo_configured() is True
    assert waffo_payment.waffo_webhook_configured() is True
    assert waffo_payment.base_url() == "https://api-sandbox.waffo.com"


# ---------------------------------------------------------------------------
# API: create order
# ---------------------------------------------------------------------------

def test_create_order_returns_waffo_cashier_url(client, waffo_env, monkeypatch):
    _clear_pancake_env(monkeypatch)
    token = _register_and_token(client)

    fake_order_action = json.dumps(
        {
            "actionType": "WEB",
            "webUrl": "https://cashier.waffo.com/orderKey123",
            "actionData": {"paymentExpiryTime": "2026-08-23T12:00:00.000Z"},
        }
    )
    fake_response = json.dumps(
        {
            "code": "0",
            "msg": "Success",
            "data": {
                "paymentRequestId": "ORD-1",
                "merchantOrderId": "ORD-1",
                "acquiringOrderId": "A2026TEST",
                "orderStatus": "AUTHORIZATION_REQUIRED",
                "orderAction": fake_order_action,
            },
        }
    )

    class FakeResponse:
        text = fake_response
        headers = {"X-SIGNATURE": _sign(fake_response)}

        def json(self):
            return json.loads(fake_response)

    captured = {}

    def fake_post(url, data=None, headers=None, timeout=None):
        captured["url"] = url
        captured["body"] = data.decode("utf-8") if isinstance(data, bytes) else data
        captured["headers"] = headers or {}
        return FakeResponse()

    with patch("src.services.waffo_payment.requests.post", side_effect=fake_post):
        res = client.post(
            "/api/payment/create-order",
            params={"token": token},
            json={"plan_id": "pro", "payment_method": "waffo"},
        )

    assert res.status_code == 200, res.text
    body = res.json()
    assert body["success"] is True
    assert body["payment_method"] == "waffo"
    assert body["checkout_url"] == "https://cashier.waffo.com/orderKey123"
    assert body["cashier_url"] == "https://cashier.waffo.com/orderKey123"
    assert body["acquiring_order_id"] == "A2026TEST"

    assert captured["url"].endswith("/api/v1/order/create")
    assert captured["headers"]["X-API-KEY"] == "waffo_api_key_test"
    assert captured["headers"]["X-API-VERSION"] == "1.0.0"
    assert captured["headers"]["X-SIGNATURE"]

    payload = json.loads(captured["body"])
    assert payload["merchantOrderId"] == body["order_id"]
    assert payload["paymentRequestId"] == body["order_id"]
    assert payload["orderCurrency"] == "CNY"
    assert payload["orderAmount"] == "2999.00"
    assert payload["orderDescription"] == "专业版 - Game Analyzer"
    assert payload["merchantInfo"]["merchantId"] == "1000000201"
    assert payload["userInfo"]["userTerminal"] == "WEB"
    assert payload["paymentInfo"]["productName"] == "ONE_TIME_PAYMENT"
    assert "/api/payment/webhook/waffo" in payload["notifyUrl"]


def test_create_order_waffo_unconfigured(client, monkeypatch):
    _clear_pancake_env(monkeypatch)
    monkeypatch.delenv("WAFFO_API_KEY", raising=False)
    token = _register_and_token(client)
    res = client.post(
        "/api/payment/create-order",
        params={"token": token},
        json={"plan_id": "pro", "payment_method": "waffo"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["success"] is False
    assert "Waffo 支付未配置" in body["message"]


def test_plans_reports_waffo_availability(client, waffo_env, monkeypatch):
    _clear_pancake_env(monkeypatch)
    token = _register_and_token(client)
    res = client.get("/api/plans", params={"token": token})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["waffo_checkout_available"] is True


# ---------------------------------------------------------------------------
# API: webhook
# ---------------------------------------------------------------------------

def _make_payment_notification(order_id: str, status: str = "PAY_SUCCESS") -> bytes:
    notification = {
        "eventType": "PAYMENT_NOTIFICATION",
        "result": {
            "paymentRequestId": order_id,
            "merchantOrderId": order_id,
            "acquiringOrderId": "A2026WEBHOOK",
            "orderStatus": status,
            "orderCurrency": "CNY",
            "orderAmount": "2999.00",
            "finalDealAmount": "2999.00",
            "orderDescription": "专业版 - Game Analyzer",
        },
    }
    return json.dumps(notification, ensure_ascii=False).encode("utf-8")


def test_waffo_webhook_marks_order_paid(client, waffo_env):
    token = _register_and_token(client)
    order_res = client.post(
        "/api/payment/create-order",
        params={"token": token},
        json={"plan_id": "pro", "payment_method": "wechat"},
    )
    assert order_res.status_code == 200, order_res.text
    order_id = order_res.json()["order_id"]

    raw = _make_payment_notification(order_id)
    wh = client.post(
        "/api/payment/webhook/waffo",
        content=raw,
        headers={"X-SIGNATURE": _sign(raw.decode("utf-8"))},
    )
    assert wh.status_code == 200, wh.text
    assert wh.json() == {"message": "success"}

    order = client.get(f"/api/payment/order/{order_id}", params={"token": token}).json()
    assert order["order"]["payment_status"] == "paid"
    assert order["order"]["transaction_id"] == "A2026WEBHOOK"


def test_waffo_webhook_rejects_bad_signature(client, waffo_env):
    token = _register_and_token(client)
    order_res = client.post(
        "/api/payment/create-order",
        params={"token": token},
        json={"plan_id": "pro", "payment_method": "wechat"},
    )
    order_id = order_res.json()["order_id"]

    raw = _make_payment_notification(order_id)
    wh = client.post(
        "/api/payment/webhook/waffo",
        content=raw,
        headers={"X-SIGNATURE": "not-a-valid-signature"},
    )
    assert wh.status_code == 200, wh.text
    assert wh.json() == {"message": "failed"}

    order = client.get(f"/api/payment/order/{order_id}", params={"token": token}).json()
    assert order["order"]["payment_status"] == "pending"


def test_waffo_webhook_ignores_non_success_event(client, waffo_env):
    token = _register_and_token(client)
    order_res = client.post(
        "/api/payment/create-order",
        params={"token": token},
        json={"plan_id": "pro", "payment_method": "wechat"},
    )
    order_id = order_res.json()["order_id"]

    raw = _make_payment_notification(order_id, status="PAY_IN_PROGRESS")
    wh = client.post(
        "/api/payment/webhook/waffo",
        content=raw,
        headers={"X-SIGNATURE": _sign(raw.decode("utf-8"))},
    )
    assert wh.status_code == 200, wh.text
    assert wh.json() == {"message": "success"}

    order = client.get(f"/api/payment/order/{order_id}", params={"token": token}).json()
    assert order["order"]["payment_status"] == "pending"

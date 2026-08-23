"""Waffo Pancake integration tests (signed HTTP mocked / local RSA roundtrips)."""

from __future__ import annotations

import base64
import hashlib
import json
import time
import uuid
from unittest.mock import patch

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from fastapi.testclient import TestClient


def _keypair():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("ascii")
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")
    return private_key, private_pem, public_pem


PRIV_KEY_OBJ, PRIVATE_PEM, PUBLIC_PEM = _keypair()


def _rsa_sign(data: str) -> str:
    sig = PRIV_KEY_OBJ.sign(data.encode("utf-8"), padding.PKCS1v15(), hashes.SHA256())
    return base64.b64encode(sig).decode("ascii")


@pytest.fixture
def client():
    from src.web_app import app

    return TestClient(app)


@pytest.fixture
def pancake_env(monkeypatch):
    monkeypatch.setenv("WAFFO_PANCAKE_MERCHANT_ID", "MER_2E02n0IyVwWWOYFUlJNBKr")
    monkeypatch.setenv("WAFFO_PANCAKE_STORE_ID", "STO_1QlHBCNATsR3yk9YNLOzZN")
    monkeypatch.setenv("WAFFO_PANCAKE_PRIVATE_KEY", PRIVATE_PEM)
    monkeypatch.setenv("WAFFO_PANCAKE_ENV", "test")
    monkeypatch.setenv("WAFFO_PANCAKE_PRODUCT_IDS", json.dumps({"pro": "PROD_test123"}))
    monkeypatch.setenv("WAFFO_PANCAKE_CURRENCY", "CNY")
    # Webhook verification uses an injected public key instead of the embedded one.
    monkeypatch.setenv("WAFFO_PANCAKE_WEBHOOK_PUBLIC_KEY", PUBLIC_PEM)


def _register_and_token(client: TestClient) -> str:
    username = f"pancake_{uuid.uuid4().hex[:8]}"
    password = "pancake-test-pass"
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
# Signing / webhook verification (SDK-equivalent)
# ---------------------------------------------------------------------------

def test_sign_request_canonical_format(pancake_env):
    from src.services import waffo_pancake

    body = '{"productId":"PROD_test123","currency":"CNY"}'
    ts = str(int(time.time()))
    sig = waffo_pancake.sign_request("POST", "/v1/actions/checkout/create-session", ts, body)
    body_hash = base64.b64encode(hashlib.sha256(body.encode()).digest()).decode()
    canonical = f"POST\n/v1/actions/checkout/create-session\n{ts}\n{body_hash}"
    # verify with our own public key
    pub = serialization.load_pem_public_key(PUBLIC_PEM.encode())
    pub.verify(
        base64.b64decode(sig),
        canonical.encode(),
        padding.PKCS1v15(),
        hashes.SHA256(),
    )


def test_verify_webhook_signature_roundtrip(pancake_env):
    from src.services import waffo_pancake

    body = json.dumps({"eventType": "order.completed", "data": {}}, ensure_ascii=False).encode()
    t = str(int(time.time() * 1000))
    sig = _rsa_sign(f"{t}.{body.decode()}")
    header = f"t={t},v1={sig}"

    assert waffo_pancake.verify_webhook_signature(body, header) is True
    assert waffo_pancake.verify_webhook_signature(body + b" ", header) is False
    assert waffo_pancake.verify_webhook_signature(body, "t=123,v1=bad") is False
    assert waffo_pancake.verify_webhook_signature(body, "") is False


def test_verify_webhook_rejects_old_timestamp(pancake_env):
    from src.services import waffo_pancake

    body = b'{"eventType":"order.completed"}'
    old_t = str(int(time.time() * 1000) - 2 * 60 * 60 * 1000)  # 2h old
    sig = _rsa_sign(f"{old_t}.{body.decode()}")
    assert waffo_pancake.verify_webhook_signature(body, f"t={old_t},v1={sig}") is False


# ---------------------------------------------------------------------------
# Checkout session creation
# ---------------------------------------------------------------------------

def test_create_checkout_session_builds_request(pancake_env):
    from src.services import waffo_pancake

    captured = {}

    def fake_api_post(path, body, timeout=20):
        captured["path"] = path
        captured["body"] = body
        return True, {
            "data": {
                "sessionId": "cs_test",
                "checkoutUrl": "https://pancake.waffo.ai/checkout/cs_test",
                "expiresAt": "2026-08-23T12:00:00.000Z",
            }
        }

    with patch("src.services.waffo_pancake.api_post", side_effect=fake_api_post):
        ok, payload = waffo_pancake.create_checkout_session(
            product_id="PROD_test123",
            order_id="ORD123",
            buyer_email="a@b.com",
            currency="CNY",
            success_url="https://app.example.com/pricing?paid=1&order_id=ORD123",
        )

    assert ok is True
    assert payload["checkout_url"] == "https://pancake.waffo.ai/checkout/cs_test"
    assert payload["provider"] == "waffo_pancake"
    assert captured["path"] == "/v1/actions/checkout/create-session"
    assert captured["body"]["productId"] == "PROD_test123"
    assert captured["body"]["currency"] == "CNY"
    assert captured["body"]["buyerEmail"] == "a@b.com"
    assert captured["body"]["orderMerchantExternalId"] == "ORD123"
    assert "successUrl" in captured["body"]


def test_create_checkout_session_missing_product(pancake_env, monkeypatch):
    monkeypatch.delenv("WAFFO_PANCAKE_PRODUCT_ID", raising=False)
    monkeypatch.setenv("WAFFO_PANCAKE_PRODUCT_IDS", "{}")
    from src.services import waffo_pancake

    ok, payload = waffo_pancake.create_checkout_session(
        product_id="",
        order_id="ORD123",
        buyer_email="a@b.com",
    )
    assert ok is False
    assert "商品 ID" in payload["error"]


# ---------------------------------------------------------------------------
# API flow through FastAPI
# ---------------------------------------------------------------------------

def test_create_order_uses_pancake_checkout_url(client, pancake_env):
    token = _register_and_token(client)

    with patch(
        "src.routers.payment_router.pancake_create_checkout_session",
        return_value=(
            True,
            {
                "checkout_url": "https://pancake.waffo.ai/checkout/cs_test",
                "session_id": "cs_test",
                "provider": "waffo_pancake",
            },
        ),
    ) as mock_create:
        res = client.post(
            "/api/payment/create-order",
            params={"token": token},
            json={"plan_id": "pro", "payment_method": "waffo"},
        )

    assert res.status_code == 200, res.text
    body = res.json()
    assert body["success"] is True
    assert body["payment_method"] == "waffo"
    assert body["provider"] == "waffo_pancake"
    assert body["checkout_url"] == "https://pancake.waffo.ai/checkout/cs_test"
    args, kwargs = mock_create.call_args
    assert kwargs["product_id"] == "PROD_test123"
    assert kwargs["order_id"] == body["order_id"]
    assert "buyer_email" in kwargs


def test_plans_reports_pancake_availability(client, pancake_env):
    token = _register_and_token(client)
    res = client.get("/api/plans", params={"token": token})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["waffo_pancake_checkout_available"] is True
    assert body["waffo_checkout_available"] is True


def _signed_order_completed_event(order_id: str) -> tuple[bytes, str]:
    payload = {
        "id": "PAY_test",
        "timestamp": "2026-08-23T12:00:00.000Z",
        "eventType": "order.completed",
        "eventId": "PAY_test",
        "storeId": "STO_1QlHBCNATsR3yk9YNLOzZN",
        "storeName": "game-analyzer",
        "mode": "test",
        "data": {
            "orderId": "ORD_pancake_test",
            "orderStatus": "completed",
            "buyerEmail": "demo@gameanalyzer.local",
            "currency": "CNY",
            "orderMerchantExternalId": order_id,
            "paymentId": "PAY_test",
            "paymentStatus": "succeeded",
        },
    }
    raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    t = str(int(time.time() * 1000))
    sig = _rsa_sign(f"{t}.{raw.decode()}")
    return raw, f"t={t},v1={sig}"


def test_pancake_webhook_marks_order_paid(client, pancake_env):
    token = _register_and_token(client)
    order_res = client.post(
        "/api/payment/create-order",
        params={"token": token},
        json={"plan_id": "pro", "payment_method": "wechat"},
    )
    assert order_res.status_code == 200, order_res.text
    order_id = order_res.json()["order_id"]

    raw, sig = _signed_order_completed_event(order_id)
    wh = client.post(
        "/api/payment/webhook/waffo-pancake",
        content=raw,
        headers={"X-Waffo-Signature": sig},
    )
    assert wh.status_code == 200, wh.text
    assert wh.json() == {"message": "success"}

    order = client.get(f"/api/payment/order/{order_id}", params={"token": token}).json()
    assert order["order"]["payment_status"] == "paid"
    assert order["order"]["transaction_id"] == "PAY_test"


def test_pancake_webhook_rejects_bad_signature(client, pancake_env):
    token = _register_and_token(client)
    order_res = client.post(
        "/api/payment/create-order",
        params={"token": token},
        json={"plan_id": "pro", "payment_method": "wechat"},
    )
    order_id = order_res.json()["order_id"]

    raw, _ = _signed_order_completed_event(order_id)
    wh = client.post(
        "/api/payment/webhook/waffo-pancake",
        content=raw,
        headers={"X-Waffo-Signature": "t=123,v1=not-valid"},
    )
    assert wh.status_code == 401, wh.text

    order = client.get(f"/api/payment/order/{order_id}", params={"token": token}).json()
    assert order["order"]["payment_status"] == "pending"

"""Waffo (https://waffo.com) one-time payment integration.

Implements the Waffo Acquiring Order REST API for creating one-time payment
orders plus the ``PAYMENT_NOTIFICATION`` webhook:

* ``POST /api/v1/order/create``  - create a one-time payment order
* ``POST /api/v1/order/inquiry`` - query the final order status
* Webhook: ``PAYMENT_NOTIFICATION`` (signature: RSA-SHA256 over the raw body)

Configuration (environment variables):

* ``WAFFO_API_KEY``       - API key from the Waffo Merchant Portal
* ``WAFFO_PRIVATE_KEY``   - merchant private key (base64 DER PKCS#8, or PEM)
* ``WAFFO_PUBLIC_KEY``    - Waffo public key (base64 DER SPKI, or PEM)
* ``WAFFO_MERCHANT_ID``   - merchant id assigned by Waffo
* ``WAFFO_ENV``           - ``sandbox`` (default) or ``production``
* ``WAFFO_ORDER_CURRENCY``- order currency, default ``CNY``

Request signing follows the official Waffo SDK: serialize the body with
``json.dumps(..., ensure_ascii=False, separators=(",", ":"))`` and sign the
exact UTF-8 bytes with SHA256WithRSA (PKCS#1 v1.5) using the merchant private
key, then base64-encode into the ``X-SIGNATURE`` header.
"""

from __future__ import annotations

import base64
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

import requests
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

_API_VERSION = "1.0.0"
_CONTENT_TYPE_JSON = "application/json"

_BASE_URLS = {
    "sandbox": "https://api-sandbox.waffo.com",
    "production": "https://api.waffo.com",
}

_ENV_VARS = (
    "WAFFO_API_KEY",
    "WAFFO_PRIVATE_KEY",
    "WAFFO_PUBLIC_KEY",
    "WAFFO_MERCHANT_ID",
)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

def waffo_env() -> str:
    return os.getenv("WAFFO_ENV", "sandbox").strip().lower()


def base_url() -> str:
    return _BASE_URLS.get(waffo_env(), _BASE_URLS["sandbox"])


def missing_config() -> list:
    return [name for name in _ENV_VARS if not os.getenv(name, "").strip()]


def waffo_configured() -> bool:
    """True when all merchant credentials required to create orders exist."""
    return not missing_config()


def waffo_webhook_configured() -> bool:
    """True when the Waffo public key (needed to verify webhooks) exists."""
    return bool(os.getenv("WAFFO_PUBLIC_KEY", "").strip())


def _public_base_url() -> str:
    return (
        os.getenv("PUBLIC_DEMO_BASE_URL", "").strip().rstrip("/")
        or os.getenv("APP_PUBLIC_URL", "").strip().rstrip("/")
        or "http://127.0.0.1:8080"
    )


# ---------------------------------------------------------------------------
# Key loading / RSA signing
# ---------------------------------------------------------------------------

def _load_private_key(private_key_input: str):
    trimmed = private_key_input.strip()
    if trimmed.startswith("-----BEGIN"):
        return serialization.load_pem_private_key(trimmed.encode("ascii"), password=None)
    der = base64.b64decode(trimmed, validate=True)
    return serialization.load_der_private_key(der, password=None)


def _load_public_key(public_key_input: str):
    trimmed = public_key_input.strip()
    if trimmed.startswith("-----BEGIN"):
        return serialization.load_pem_public_key(trimmed.encode("ascii"))
    der = base64.b64decode(trimmed, validate=True)
    return serialization.load_der_public_key(der)


def sign(data: str, private_key: Optional[str] = None) -> str:
    """SHA256WithRSA (PKCS#1 v1.5) signature over UTF-8 data, base64 encoded."""
    key_input = private_key or os.getenv("WAFFO_PRIVATE_KEY", "")
    if not key_input:
        raise ValueError("WAFFO_PRIVATE_KEY not configured")
    key = _load_private_key(key_input)
    signature = key.sign(data.encode("utf-8"), padding.PKCS1v15(), hashes.SHA256())
    return base64.b64encode(signature).decode("ascii")


def verify_signature(data: str, signature: str, public_key: Optional[str] = None) -> bool:
    """Verify an RSA-SHA256 signature using the Waffo public key."""
    key_input = public_key or os.getenv("WAFFO_PUBLIC_KEY", "")
    if not key_input or not signature:
        return False
    try:
        key = _load_public_key(key_input)
        sig_bytes = base64.b64decode(signature, validate=True)
        key.verify(sig_bytes, data.encode("utf-8"), padding.PKCS1v15(), hashes.SHA256())
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False


def _now_utc() -> str:
    now = datetime.now(timezone.utc)
    return f"{now:%Y-%m-%dT%H:%M:%S}.{now.microsecond // 1000:03d}Z"


# ---------------------------------------------------------------------------
# Order creation
# ---------------------------------------------------------------------------

def create_payment_order(
    *,
    order_id: str,
    plan_name: str,
    amount_yuan: int,
    username: str,
    user_email: str = "",
    currency: Optional[str] = None,
) -> Tuple[bool, Dict[str, Any]]:
    """
    Create a Waffo one-time payment order and return the hosted cashier URL.

    Returns ``(True, {...})`` with ``checkout_url``/``acquiring_order_id`` on
    success, or ``(False, {"error": ...})`` on failure.
    """
    if not waffo_configured():
        missing = missing_config()
        return False, {"error": f"Waffo 支付未配置: {', '.join(missing)}"}

    base = _public_base_url()
    currency = (currency or os.getenv("WAFFO_ORDER_CURRENCY", "CNY")).strip().upper()

    payload = {
        "paymentRequestId": order_id,
        "merchantOrderId": order_id,
        "orderCurrency": currency,
        "orderAmount": f"{max(amount_yuan, 1):.2f}",
        "orderDescription": f"{plan_name} - Game Analyzer",
        "orderRequestedAt": _now_utc(),
        "notifyUrl": f"{base}/api/payment/webhook/waffo",
        "successRedirectUrl": f"{base}/pricing?paid=1&order_id={order_id}",
        "failedRedirectUrl": f"{base}/pricing?cancelled=1",
        "cancelRedirectUrl": f"{base}/pricing?cancelled=1",
        "merchantInfo": {"merchantId": os.getenv("WAFFO_MERCHANT_ID", "").strip()},
        "userInfo": {
            "userId": username,
            # Required by Waffo; fall back to a unique placeholder when the
            # merchant has not collected an email address.
            "userEmail": user_email or f"{username}@gameanalyzer.local",
            "userTerminal": "WEB",
        },
        "paymentInfo": {"productName": "ONE_TIME_PAYMENT"},
        "goodsInfo": {"goodsName": plan_name, "goodsUrl": f"{base}/pricing"},
    }

    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    headers = {
        "Content-Type": _CONTENT_TYPE_JSON,
        "X-API-KEY": os.getenv("WAFFO_API_KEY", "").strip(),
        "X-SIGNATURE": sign(body),
        "X-API-VERSION": _API_VERSION,
    }

    url = f"{base_url()}/api/v1/order/create"
    try:
        response = requests.post(url, data=body.encode("utf-8"), headers=headers, timeout=15)
    except requests.RequestException as exc:
        return False, {"error": f"Waffo 请求失败: {exc}"}

    response_body = response.text
    response_signature = response.headers.get("X-SIGNATURE", "")
    if response_signature and not verify_signature(response_body, response_signature):
        return False, {"error": "Waffo 响应签名验证失败"}

    try:
        result = response.json()
    except ValueError:
        return False, {"error": f"Waffo 响应不是有效 JSON: {response_body[:200]}"}

    if result.get("code") != "0":
        return False, {"error": result.get("msg") or f"Waffo 下单失败(code={result.get('code')})"}

    data = result.get("data") or {}
    checkout_url = _extract_cashier_url(data.get("orderAction", ""))
    if not checkout_url:
        return False, {"error": "Waffo 未返回收银台地址(orderAction.webUrl)"}

    return True, {
        "checkout_url": checkout_url,
        "acquiring_order_id": data.get("acquiringOrderId", ""),
        "order_status": data.get("orderStatus", ""),
        "provider": "waffo",
    }


def _extract_cashier_url(order_action: str) -> Optional[str]:
    """Parse the ``orderAction`` JSON string and return the cashier web URL."""
    if not order_action:
        return None
    try:
        parsed = json.loads(order_action)
    except (ValueError, TypeError):
        return None
    if not isinstance(parsed, dict):
        return None
    web_url = parsed.get("webUrl")
    if isinstance(web_url, str) and web_url:
        return web_url
    deeplink_url = parsed.get("deeplinkUrl")
    if isinstance(deeplink_url, str) and deeplink_url:
        return deeplink_url
    return None


# ---------------------------------------------------------------------------
# Order inquiry
# ---------------------------------------------------------------------------

def inquiry_order(order_id: str) -> Tuple[bool, Dict[str, Any]]:
    """Query the final status of a Waffo order by merchant order id."""
    if not waffo_configured():
        return False, {"error": "Waffo 支付未配置"}

    payload = {"merchantOrderId": order_id}
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    headers = {
        "Content-Type": _CONTENT_TYPE_JSON,
        "X-API-KEY": os.getenv("WAFFO_API_KEY", "").strip(),
        "X-SIGNATURE": sign(body),
        "X-API-VERSION": _API_VERSION,
    }
    url = f"{base_url()}/api/v1/order/inquiry"
    try:
        response = requests.post(url, data=body.encode("utf-8"), headers=headers, timeout=15)
    except requests.RequestException as exc:
        return False, {"error": f"Waffo 请求失败: {exc}"}

    response_body = response.text
    response_signature = response.headers.get("X-SIGNATURE", "")
    if response_signature and not verify_signature(response_body, response_signature):
        return False, {"error": "Waffo 响应签名验证失败"}

    try:
        result = response.json()
    except ValueError:
        return False, {"error": f"Waffo 响应不是有效 JSON: {response_body[:200]}"}

    if result.get("code") != "0":
        return False, {"error": result.get("msg") or f"Waffo 查询失败(code={result.get('code')})"}
    return True, {"data": result.get("data") or {}}


# ---------------------------------------------------------------------------
# Webhook parsing
# ---------------------------------------------------------------------------

def parse_notification(raw_body: bytes) -> Dict[str, Any]:
    """Parse the webhook body into a notification dict."""
    return json.loads(raw_body.decode("utf-8"))


def payment_result_from_notification(notification: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Extract a payment result from a ``PAYMENT_NOTIFICATION`` webhook.

    Returns ``None`` for non-payment events. The result mirrors the order
    inquiry response (``merchantOrderId``, ``acquiringOrderId``,
    ``orderStatus``, ...).
    """
    if notification.get("eventType") != "PAYMENT_NOTIFICATION":
        return None
    result = notification.get("result")
    if not isinstance(result, dict):
        return None
    return {
        "order_id": result.get("merchantOrderId", ""),
        "transaction_id": result.get("acquiringOrderId", ""),
        "order_status": result.get("orderStatus", ""),
        "payment_request_id": result.get("paymentRequestId", ""),
    }

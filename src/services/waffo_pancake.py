"""Waffo Pancake (https://docs.waffo.ai) payment integration for Python.

Waffo Pancake is the merchant-of-record payment platform exposed through the
official TypeScript SDK ``@waffo/pancake-ts``. This Python module re-implements
the SDK's exact wire protocol (request signing, webhook signature verification
and the embedded test/prod webhook public keys) so the FastAPI backend can use
Pancake without a Node.js sidecar:

* API base:  ``https://api.waffo.ai``
* Auth:      ``X-Merchant-Id`` / ``X-Timestamp`` / ``X-Signature``
* Signing:   ``canonical = METHOD\\nPATH\\nTIMESTAMP\\nbase64(sha256(body))``,
             then RSA-SHA256 (PKCS#1 v1.5), base64 encoded.
* Webhook:   ``X-Waffo-Signature: t=<ms>,v1=<base64 sig>`` over ``f"{t}.{raw}"``,
             verified with the environment's Waffo public key
             (test/prod keys embedded below, overridable via env).

Configuration (environment variables, all optional unless noted):

* ``WAFFO_PANCAKE_MERCHANT_ID``   - merchant id ``MER_xxx`` (required)
* ``WAFFO_PANCAKE_PRIVATE_KEY``   - RSA private key (base64 DER PKCS#8 or PEM)
* ``WAFFO_PANCAKE_STORE_ID``      - store id ``STO_xxx`` (required)
* ``WAFFO_PANCAKE_ENV``           - ``test`` (default) or ``prod``
* ``WAFFO_PANCAKE_PRODUCT_ID``    - default onetime product ``PROD_xxx``
* ``WAFFO_PANCAKE_PRODUCT_IDS``   - JSON map ``{"pro": "PROD_xxx", ...}``
* ``WAFFO_PANCAKE_CURRENCY``      - checkout currency, default ``CNY``
* ``WAFFO_PANCAKE_WEBHOOK_PUBLIC_KEY`` - optional override for webhook verify
* ``WAFFO_PANCAKE_API_KEY``       - informational only (not sent on requests)
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import time
from typing import Any, Dict, Optional, Tuple

import requests
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

_API_BASE = "https://api.waffo.ai"

# Webhook public keys embedded in @waffo/pancake-ts (dist/index.js).
_TEST_PUBLIC_KEY = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAxnmRY6yMMA3lVqmAU6ZG
b1sjL/+r/z6E+ZjkXaDAKiqOhk9rpazni0bNsGXwmftTPk9jy2wn+j6JHODD/WH/
SCnSfvKkLIjy4Hk7BuCgB174C0ydan7J+KgXLkOwgCAxxB68t2tezldwo74ZpXgn
F49opzMvQ9prEwIAWOE+kV9iK6gx/AckSMtHIHpUesoPDkldpmFHlB2qpf1vsFTZ
5kD6DmGl+2GIVK01aChy2lk8pLv0yUMu18v44sLkO5M44TkGPJD9qG09wrvVG2wp
OTVCn1n5pP8P+HRLcgzbUB3OlZVfdFurn6EZwtyL4ZD9kdkQ4EZE/9inKcp3c1h4
xwIDAQAB
-----END PUBLIC KEY-----"""

_PROD_PUBLIC_KEY = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAz+xApdTIb4ua+DgZKQ54
iBsD82ybyhGCLRETONW4Jgbb3A8DUM1LqBk6r/CmTOCHqLalTQHNigvP3R5zkDNX
iRJz6gA4MJ/+8K0+mnEE2RISQzN+Qu65TNd6svb+INm/kMaftY4uIXr6y6kchtTJ
dwnQhcKdAL2v7h7IFnkVelQsKxDdb2PqX8xX/qwd01iXvMcpCCaXovUwZsxH2QN5
ZKBTseJivbhUeyJCco4fdUyxOMHe2ybCVhyvim2uxAl1nkvL5L8RCWMCAV55LLo0
9OhmLahz/DYNu13YLVP6dvIT09ZFBYU6Owj1NxdinTynlJCFS9VYwBgmftosSE1U
dwIDAQAB
-----END PUBLIC KEY-----"""


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

def pancake_env() -> str:
    return os.getenv("WAFFO_PANCAKE_ENV", "test").strip().lower()


def merchant_id() -> str:
    return os.getenv("WAFFO_PANCAKE_MERCHANT_ID", "").strip()


def store_id() -> str:
    return os.getenv("WAFFO_PANCAKE_STORE_ID", "").strip()


def default_product_id() -> str:
    return os.getenv("WAFFO_PANCAKE_PRODUCT_ID", "").strip()


def product_ids_map() -> Dict[str, str]:
    raw = os.getenv("WAFFO_PANCAKE_PRODUCT_IDS", "").strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        return {str(k): str(v) for k, v in parsed.items()} if isinstance(parsed, dict) else {}
    except ValueError:
        return {}


def product_id_for_plan(plan_id: str) -> str:
    return product_ids_map().get(plan_id) or default_product_id()


def pancake_configured() -> bool:
    return bool(merchant_id() and store_id() and os.getenv("WAFFO_PANCAKE_PRIVATE_KEY", "").strip())


def pancake_webhook_configured() -> bool:
    return bool(merchant_id())


# ---------------------------------------------------------------------------
# Key handling / signing
# ---------------------------------------------------------------------------

def _normalize_private_key(raw: str) -> bytes:
    """Return the DER bytes of an RSA private key from base64 DER or PEM."""
    trimmed = raw.strip()
    if trimmed.startswith("-----BEGIN"):
        return serialization.load_pem_private_key(trimmed.encode("ascii"), password=None).private_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    der = base64.b64decode(trimmed, validate=True)
    return der


def _load_private_key(raw: str):
    trimmed = raw.strip()
    if trimmed.startswith("-----BEGIN"):
        return serialization.load_pem_private_key(trimmed.encode("ascii"), password=None)
    return serialization.load_der_private_key(base64.b64decode(trimmed, validate=True), password=None)


def _load_public_key(raw: str):
    trimmed = raw.strip()
    if trimmed.startswith("-----BEGIN"):
        return serialization.load_pem_public_key(trimmed.encode("ascii"))
    return serialization.load_der_public_key(base64.b64decode(trimmed, validate=True))


def sign_request(method: str, path: str, timestamp: str, body: str, private_key: Optional[str] = None) -> str:
    """Sign a canonical request the same way @waffo/pancake-ts does."""
    key_input = private_key or os.getenv("WAFFO_PANCAKE_PRIVATE_KEY", "")
    if not key_input:
        raise ValueError("WAFFO_PANCAKE_PRIVATE_KEY not configured")
    body_hash = base64.b64encode(hashlib.sha256(body.encode("utf-8")).digest()).decode("ascii")
    canonical = f"{method}\n{path}\n{timestamp}\n{body_hash}"
    key = _load_private_key(key_input)
    signature = key.sign(canonical.encode("utf-8"), padding.PKCS1v15(), hashes.SHA256())
    return base64.b64encode(signature).decode("ascii")


def api_post(path: str, body: Dict[str, Any], timeout: int = 20) -> Tuple[bool, Dict[str, Any]]:
    """Signed POST to api.waffo.ai. Returns (ok, envelope)."""
    if not pancake_configured():
        return False, {"errors": [{"message": "Waffo Pancake 未配置"}]}
    body_str = json.dumps(body, ensure_ascii=False, separators=(",", ":"))
    timestamp = str(int(time.time()))
    signature = sign_request("POST", path, timestamp, body_str)
    headers = {
        "Content-Type": "application/json",
        "X-Merchant-Id": merchant_id(),
        "X-Timestamp": timestamp,
        "X-Signature": signature,
    }
    url = f"{_API_BASE}{path}"
    try:
        response = requests.post(url, data=body_str.encode("utf-8"), headers=headers, timeout=timeout)
    except requests.RequestException as exc:
        return False, {"errors": [{"message": f"Waffo Pancake 请求失败: {exc}"}]}
    try:
        envelope = response.json()
    except ValueError:
        return False, {
            "status": response.status_code,
            "errors": [{"message": f"Non-JSON response from {path}"}],
        }
    envelope.setdefault("status", response.status_code)
    return True, envelope


def graphql_query(query: str, variables: Optional[Dict[str, Any]] = None) -> Tuple[bool, Dict[str, Any]]:
    """Run a read-only GraphQL query. Returns (ok, data_dict)."""
    ok, envelope = api_post("/v1/graphql", {"query": query, "variables": variables or {}})
    if not ok:
        return False, envelope
    if envelope.get("errors"):
        return False, envelope
    return True, envelope.get("data") or {}


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------

def list_products(sid: str = "") -> Tuple[bool, Dict[str, Any]]:
    """List one-time products of a store (test/prod depends on the API key)."""
    sid = sid or store_id()
    query = """
    query ListProducts($storeId: String!) {
      store(id: $storeId) {
        id
        onetimeProducts {
          id
          name
          status
          metadata
          prices { currency priceInfo { amount taxCategory } }
        }
      }
    }
    """
    ok, data = graphql_query(query, {"storeId": sid})
    if not ok:
        return False, data
    store = data.get("store") or {}
    return True, {"onetimeProducts": store.get("onetimeProducts") or []}


def create_onetime_product(
    *,
    name: str,
    amount: str,
    currency: str = "CNY",
    description: Optional[str] = None,
    success_url: Optional[str] = None,
    metadata: Optional[Dict[str, str]] = None,
    sid: str = "",
) -> Tuple[bool, Dict[str, Any]]:
    """Create a one-time product in the store. Returns (ok, envelope)."""
    sid = sid or store_id()
    body: Dict[str, Any] = {
        "storeId": sid,
        "name": name,
        "prices": {
            currency: {
                "amount": amount,
                "taxIncluded": True,
                "taxCategory": "saas",
            }
        },
        "metadata": metadata or {},
    }
    if description:
        body["description"] = description
    if success_url:
        body["successUrl"] = success_url
    return api_post("/v1/actions/onetime-product/create-product", body)


# ---------------------------------------------------------------------------
# Checkout
# ---------------------------------------------------------------------------

def create_checkout_session(
    *,
    product_id: str,
    order_id: str,
    buyer_email: str,
    currency: str = "CNY",
    success_url: Optional[str] = None,
    language: str = "zh-Hans",
) -> Tuple[bool, Dict[str, Any]]:
    """
    Create a checkout session and return the hosted checkout URL.

    Returns (True, {"checkout_url", "session_id", "expires_at"}) on success,
    or (False, {"error": ...}).
    """
    if not pancake_configured():
        return False, {"error": "Waffo Pancake 未配置"}
    if not product_id:
        return False, {"error": "未配置 Waffo Pancake 商品 ID (WAFFO_PANCAKE_PRODUCT_ID)"}

    body: Dict[str, Any] = {
        "productId": product_id,
        "currency": currency,
        "buyerEmail": buyer_email,
        "language": language,
        "orderMerchantExternalId": order_id,
    }
    if success_url:
        body["successUrl"] = success_url

    ok, envelope = api_post("/v1/actions/checkout/create-session", body)
    if not ok:
        return False, {"error": envelope.get("errors") or "Waffo Pancake 请求失败"}
    if envelope.get("errors"):
        msgs = "; ".join(e.get("message", "") for e in envelope["errors"])
        return False, {"error": f"Waffo Pancake 下单失败: {msgs}"}

    data = envelope.get("data") or {}
    checkout_url = data.get("checkoutUrl") or ""
    if not checkout_url:
        return False, {"error": "Waffo Pancake 未返回收银台地址"}
    return True, {
        "checkout_url": checkout_url,
        "session_id": data.get("sessionId", ""),
        "expires_at": data.get("expiresAt", ""),
        "provider": "waffo_pancake",
    }


# ---------------------------------------------------------------------------
# Webhooks
# ---------------------------------------------------------------------------

def list_webhooks(sid: str = "") -> Tuple[bool, Dict[str, Any]]:
    """List configured webhooks via GraphQL (filtered by env automatically)."""
    sid = sid or store_id()
    query = """
    query GetStoreWebhooks($storeId: String!) {
      store(id: $storeId) {
        storeWebhooks {
          id
          channel
          url
          events
          testMode
          createdAt
        }
      }
    }
    """
    return graphql_query(query, {"storeId": sid})


def add_webhook(
    *,
    url: str,
    events: Optional[list] = None,
    sid: str = "",
    test_mode: Optional[bool] = None,
) -> Tuple[bool, Dict[str, Any]]:
    """Register an HTTP webhook on the store. Returns (ok, envelope)."""
    sid = sid or store_id()
    body = {
        "storeId": sid,
        "channel": "http",
        "url": url,
        "events": events or ["order.completed", "refund.succeeded"],
        "testMode": pancake_env() == "test" if test_mode is None else test_mode,
    }
    return api_post("/v1/actions/store/add-webhook", body)


def update_webhook(webhook_id: str, url: Optional[str] = None, events: Optional[list] = None) -> Tuple[bool, Dict[str, Any]]:
    """Update a webhook's URL and/or subscribed events."""
    body: Dict[str, Any] = {"id": webhook_id}
    if url:
        body["url"] = url
    if events is not None:
        body["events"] = events
    return api_post("/v1/actions/store/update-webhook", body)


def remove_webhook(webhook_id: str) -> Tuple[bool, Dict[str, Any]]:
    return api_post("/v1/actions/store/remove-webhook", {"id": webhook_id})


def _webhook_public_key(environment: Optional[str] = None) -> str:
    override = os.getenv("WAFFO_PANCAKE_WEBHOOK_PUBLIC_KEY", "").strip()
    if override:
        return override
    env = (environment or pancake_env()).strip().lower()
    return _PROD_PUBLIC_KEY if env == "prod" else _TEST_PUBLIC_KEY


def verify_webhook_signature(
    raw_body: bytes,
    signature_header: str,
    environment: Optional[str] = None,
    tolerance_ms: int = 45 * 60 * 1000,
    future_tolerance_ms: int = 60 * 1000,
) -> bool:
    """Verify the X-Waffo-Signature header over the raw body (SDK-equivalent)."""
    if not signature_header:
        return False
    t, v1 = None, None
    for pair in signature_header.split(","):
        if "=" not in pair:
            continue
        key, _, value = pair.partition("=")
        key = key.strip()
        value = value.strip()
        if key == "t":
            t = value
        elif key == "v1":
            v1 = value
    if not t or not v1:
        return False
    try:
        timestamp_ms = int(t)
    except ValueError:
        return False
    if tolerance_ms > 0:
        age_ms = int(time.time() * 1000) - timestamp_ms
        if age_ms > tolerance_ms or age_ms < -future_tolerance_ms:
            return False

    signature_input = f"{t}.{raw_body.decode('utf-8')}"
    try:
        public_key = _load_public_key(_webhook_public_key(environment))
        sig_bytes = base64.b64decode(v1, validate=True)
        public_key.verify(sig_bytes, signature_input.encode("utf-8"), padding.PKCS1v15(), hashes.SHA256())
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False


def parse_webhook_event(
    raw_body: bytes,
    signature_header: str,
    environment: Optional[str] = None,
) -> Dict[str, Any]:
    """Verify and parse a webhook event. Raises ValueError on invalid input."""
    if not verify_webhook_signature(raw_body, signature_header, environment=environment):
        raise ValueError("Invalid webhook signature")
    return json.loads(raw_body.decode("utf-8"))

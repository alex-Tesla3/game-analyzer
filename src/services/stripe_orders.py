"""Optional Stripe Checkout for subscription orders (sandbox / production)."""

from __future__ import annotations

import os
from typing import Any, Dict, Optional, Tuple

_STRIPE_IMPORT_ERROR: Optional[str] = None

try:
    import stripe as _stripe
except ImportError as exc:
    _stripe = None
    _STRIPE_IMPORT_ERROR = str(exc)


def stripe_configured() -> bool:
    return bool(os.getenv("STRIPE_SECRET_KEY", "").strip()) and _stripe is not None


def stripe_webhook_configured() -> bool:
    return bool(os.getenv("STRIPE_WEBHOOK_SECRET", "").strip()) and _stripe is not None


def stripe_import_error() -> Optional[str]:
    return _STRIPE_IMPORT_ERROR


def _public_base_url() -> str:
    return (
        os.getenv("PUBLIC_DEMO_BASE_URL", "").strip().rstrip("/")
        or os.getenv("APP_PUBLIC_URL", "").strip().rstrip("/")
        or "http://127.0.0.1:8080"
    )


def create_checkout_session(
    *,
    order_id: str,
    plan_name: str,
    amount_yuan: int,
    username: str,
) -> Tuple[bool, Dict[str, Any]]:
    """
    Create a Stripe Checkout Session (one-time payment in CNY).
    Returns (success, payload with checkout_url / session_id or error).
    """
    if not stripe_configured():
        err = stripe_import_error() or "STRIPE_SECRET_KEY not set"
        return False, {"error": err}

    base = _public_base_url()
    success_url = f"{base}/pricing?paid=1&order_id={order_id}"
    cancel_url = f"{base}/pricing?cancelled=1"

    _stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "").strip()
    try:
        session = _stripe.checkout.Session.create(
            mode="payment",
            payment_method_types=["card"],
            line_items=[
                {
                    "price_data": {
                        "currency": "cny",
                        "unit_amount": max(amount_yuan, 1) * 100,
                        "product_data": {"name": plan_name},
                    },
                    "quantity": 1,
                }
            ],
            metadata={
                "order_id": order_id,
                "username": username,
            },
            success_url=success_url,
            cancel_url=cancel_url,
        )
        return True, {
            "checkout_url": session.url,
            "session_id": session.id,
            "provider": "stripe",
        }
    except Exception as exc:
        return False, {"error": str(exc), "provider": "stripe"}


def construct_webhook_event(payload: bytes, signature_header: str) -> Any:
    """Verify Stripe-Signature and return Event."""
    if not stripe_webhook_configured():
        raise RuntimeError("STRIPE_WEBHOOK_SECRET not configured")
    secret = os.getenv("STRIPE_WEBHOOK_SECRET", "").strip()
    return _stripe.Webhook.construct_event(payload, signature_header or "", secret)


def order_id_from_checkout_event(event: Any) -> Optional[str]:
    if getattr(event, "type", None) != "checkout.session.completed":
        return None
    obj = event.data.object
    meta = getattr(obj, "metadata", None) or {}
    if isinstance(meta, dict):
        return meta.get("order_id")
    return getattr(meta, "get", lambda k, d=None: None)("order_id")

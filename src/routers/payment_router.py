"""Payment and subscription plan routes."""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request

from auth import PLANS
from database import OperationLogRepository, OrderRepository
from src.commercial_config import payment_mode, payment_mode_message, stripe_checkout_available
from src.plans_catalog import list_plans_for_api
from src.services.stripe_orders import (
    construct_webhook_event,
    create_checkout_session,
    order_id_from_checkout_event,
    stripe_webhook_configured,
)
from src.web_common import get_current_user, mark_order_paid, verify_payment_signature

router = APIRouter(tags=["payment"])


@router.get("/api/plans")
async def get_plans(token: Optional[str] = Query(None)):
    if not token:
        raise HTTPException(status_code=401, detail="Token required")
    await get_current_user(token)

    mode = payment_mode()
    return {
        "success": True,
        "payment_mode": mode,
        "stripe_checkout_available": stripe_checkout_available(),
        "message": payment_mode_message(mode),
        "plans": list_plans_for_api(),
    }


@router.post("/api/payment/create-order")
async def create_payment_order(request: Request, token: Optional[str] = Query(None)):
    if not token:
        raise HTTPException(status_code=401, detail="Token required")

    current_user = await get_current_user(token)
    body = await request.json()

    plan_id = body.get("plan_id")
    payment_method = body.get("payment_method", "wechat")

    if plan_id not in PLANS:
        return {"success": False, "message": "无效的订阅计划"}

    plan = PLANS[plan_id]
    if plan.price == 0:
        return {"success": False, "message": "该计划无需支付"}

    order_id = OrderRepository.create_order(
        username=current_user.username,
        plan_id=plan_id,
        amount=plan.price,
        payment_method=payment_method,
    )

    if not order_id:
        return {"success": False, "message": "创建订单失败"}

    OperationLogRepository.log(
        current_user.username, "create_order", f"Created order: {order_id} for plan: {plan_id}"
    )

    if payment_method == "stripe":
        ok, payload = create_checkout_session(
            order_id=order_id,
            plan_name=plan.name,
            amount_yuan=int(plan.price),
            username=current_user.username,
        )
        if not ok:
            return {
                "success": False,
                "message": payload.get("error") or "Stripe 结账创建失败",
            }
        return {
            "success": True,
            "order_id": order_id,
            "amount": plan.price,
            "payment_method": "stripe",
            "checkout_url": payload.get("checkout_url"),
            "session_id": payload.get("session_id"),
        }

    qr_code_url = (
        f"https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={order_id}"
    )

    return {
        "success": True,
        "order_id": order_id,
        "amount": plan.price,
        "qr_code_url": qr_code_url,
        "payment_method": payment_method,
    }


@router.get("/api/payment/order/{order_id}")
async def get_order_status(order_id: str, token: Optional[str] = Query(None)):
    if not token:
        raise HTTPException(status_code=401, detail="Token required")

    current_user = await get_current_user(token)
    order = OrderRepository.get_order(order_id)

    if not order:
        return {"success": False, "message": "订单不存在"}

    if order["username"] != current_user.username:
        return {"success": False, "message": "无权限查看该订单"}

    return {"success": True, "order": order}


@router.post("/api/payment/confirm")
async def confirm_payment(request: Request, token: Optional[str] = Query(None)):
    if not token:
        raise HTTPException(status_code=401, detail="Token required")

    current_user = await get_current_user(token)
    body = await request.json()
    app_env = os.getenv("APP_ENV", "development").lower()
    payment_test_mode = os.getenv(
        "PAYMENT_TEST_MODE",
        "false" if app_env == "production" else "true",
    ).lower() in {"1", "true", "yes", "on"}

    if not payment_test_mode and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="生产环境仅允许服务端支付回调确认订单")

    order_id = body.get("order_id")
    transaction_id = body.get("transaction_id", f"TXN{datetime.now().strftime('%Y%m%d%H%M%S')}")

    order = OrderRepository.get_order(order_id)
    if not order:
        return {"success": False, "message": "订单不存在"}

    if order["username"] != current_user.username:
        return {"success": False, "message": "无权限操作该订单"}

    if order["payment_status"] == "paid":
        return {"success": True, "message": "订单已支付"}

    payment_result = mark_order_paid(order, transaction_id)

    return {
        "success": True,
        "message": "支付成功",
        "plan_id": payment_result["plan_id"],
        "expires_at": payment_result["expires_at"],
    }


@router.post("/api/payment/webhook")
async def payment_webhook(request: Request):
    webhook_secret = os.getenv("PAYMENT_WEBHOOK_SECRET", "")
    app_env = os.getenv("APP_ENV", "development").lower()
    if app_env == "production" and not webhook_secret:
        raise HTTPException(status_code=500, detail="支付回调密钥未配置")

    raw_body = await request.body()
    signature = request.headers.get("X-Payment-Signature", "")
    if webhook_secret and not verify_payment_signature(raw_body, signature, webhook_secret):
        raise HTTPException(status_code=401, detail="支付回调签名无效")

    try:
        body = json.loads(raw_body.decode("utf-8"))
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="无效的支付回调数据")

    order_id = body.get("order_id")
    payment_status = body.get("payment_status")
    transaction_id = body.get("transaction_id") or f"PAY{datetime.now().strftime('%Y%m%d%H%M%S')}"

    if payment_status != "paid":
        return {"success": True, "message": "非支付成功事件已忽略"}

    order = OrderRepository.get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")

    if order["payment_status"] == "paid":
        return {"success": True, "message": "订单已支付"}

    payment_result = mark_order_paid(order, transaction_id)
    return {
        "success": True,
        "message": "支付回调处理成功",
        "plan_id": payment_result["plan_id"],
        "expires_at": payment_result["expires_at"],
    }


@router.post("/api/payment/webhook/stripe")
async def stripe_payment_webhook(request: Request):
    if not stripe_webhook_configured():
        raise HTTPException(status_code=500, detail="Stripe Webhook 未配置")

    raw_body = await request.body()
    signature = request.headers.get("Stripe-Signature", "")

    try:
        event = construct_webhook_event(raw_body, signature)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Stripe 签名验证失败: {exc}") from exc

    order_id = order_id_from_checkout_event(event)
    if not order_id:
        return {"success": True, "message": "非 checkout.session.completed 事件已忽略"}

    order = OrderRepository.get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")

    if order["payment_status"] == "paid":
        return {"success": True, "message": "订单已支付"}

    session_id = getattr(getattr(event, "data", None), "object", None)
    txn = getattr(session_id, "id", None) or f"stripe_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    payment_result = mark_order_paid(order, txn)
    return {
        "success": True,
        "message": "Stripe 支付回调处理成功",
        "plan_id": payment_result["plan_id"],
        "expires_at": payment_result["expires_at"],
    }


@router.get("/api/payment/orders")
async def get_user_orders(token: Optional[str] = Query(None)):
    if not token:
        raise HTTPException(status_code=401, detail="Token required")

    current_user = await get_current_user(token)
    orders = OrderRepository.get_user_orders(current_user.username)

    return {"success": True, "orders": orders}

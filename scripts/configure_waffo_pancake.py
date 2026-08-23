#!/usr/bin/env python3
"""One-shot Waffo Pancake setup: verify merchant/store, ensure a Pro product,
register the order.completed webhook, and write WAFFO_PANCAKE_* into .env.

Usage:
    python3 scripts/configure_waffo_pancake.py [--public-url https://app.example.com]

Requirements: WAFFO_PANCAKE_MERCHANT_ID, WAFFO_PANCAKE_PRIVATE_KEY,
WAFFO_PANCAKE_STORE_ID (env or .env). Uses the test API key if set in .env.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from src.env_loader import load_env_file  # noqa: E402

load_env_file(str(ROOT / ".env"))

from src.services import waffo_pancake  # noqa: E402

PRO_PRODUCT_NAME = "专业版 - Game Analyzer (年费)"
PRO_PRODUCT_AMOUNT = "2999.00"
PRO_PRODUCT_METADATA = {"planId": "pro", "app": "game-analyzer"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Configure Waffo Pancake for game-analyzer")
    parser.add_argument(
        "--public-url",
        default=os.getenv("WAFFO_WEBHOOK_URL")
        or os.getenv("APP_PUBLIC_URL")
        or os.getenv("PUBLIC_DEMO_BASE_URL")
        or "http://127.0.0.1:8080",
        help="Public base URL of this app (webhook is registered under it)",
    )
    args = parser.parse_args()

    if not waffo_pancake.pancake_configured():
        print("错误: 未配置 WAFFO_PANCAKE_MERCHANT_ID / WAFFO_PANCAKE_PRIVATE_KEY / WAFFO_PANCAKE_STORE_ID")
        return 1

    print(f"Merchant : {waffo_pancake.merchant_id()}")
    print(f"Store    : {waffo_pancake.store_id()}")
    print(f"Env      : {waffo_pancake.pancake_env()}")
    print(f"API Base : {waffo_pancake._API_BASE}")

    # 1. Verify store access
    ok, data = waffo_pancake.graphql_query(
        "query Store($id: String!) { store(id: $id) { id name status } }",
        {"id": waffo_pancake.store_id()},
    )
    if not ok:
        print("无法查询店铺:", json.dumps(data, ensure_ascii=False)[:500])
        return 1
    store = (data.get("store") or {})
    if not store:
        print("错误: 店铺不存在或 API Key 无权访问")
        return 1
    print(f"店铺     : {store.get('name')} ({store.get('id')}) status={store.get('status')}")

    # 2. Ensure the Pro one-time product exists
    product_id = waffo_pancake.product_id_for_plan("pro")
    if not product_id:
        ok, products = waffo_pancake.list_products()
        if not ok:
            print("无法列出商品:", json.dumps(products, ensure_ascii=False)[:500])
            return 1
        items = (products.get("onetimeProducts") or [])
        for item in items:
            meta = item.get("metadata") or {}
            if isinstance(meta, str):
                try:
                    meta = json.loads(meta)
                except ValueError:
                    meta = {}
            if meta.get("planId") == "pro":
                product_id = item.get("id")
                print(f"发现已存在的 Pro 商品: {item.get('name')} ({product_id})")
                break
        if not product_id:
            ok, result = waffo_pancake.create_onetime_product(
                name=PRO_PRODUCT_NAME,
                amount=PRO_PRODUCT_AMOUNT,
                currency="CNY",
                description="游戏数据分析引擎 · 专业版年度订阅（一次性支付，开通 1 年权益）",
                success_url=(
                    f"{args.public_url.rstrip('/')}/pricing?paid=1"
                    if args.public_url.startswith("http")
                    else None
                ),
                metadata=PRO_PRODUCT_METADATA,
            )
            if not ok or result.get("errors"):
                print("创建商品失败:", json.dumps(result, ensure_ascii=False)[:500])
                return 1
            product_id = (result.get("data") or {}).get("product", {}).get("id")
            if not product_id:
                print("创建商品响应缺少 product.id:", json.dumps(result, ensure_ascii=False)[:500])
                return 1
            print(f"已创建 Pro 商品: {PRO_PRODUCT_NAME} ({product_id})")
    else:
        print(f"使用配置中的 Pro 商品 ID: {product_id}")

    # 3. Register the order.completed webhook (idempotent)
    webhook_url = f"{args.public_url.rstrip('/')}/api/payment/webhook/waffo-pancake"
    ok, hooks = waffo_pancake.list_webhooks()
    if not ok:
        print("无法列出 Webhook:", json.dumps(hooks, ensure_ascii=False)[:500])
        return 1
    store_hooks = ((hooks.get("store") or {}).get("storeWebhooks") or [])
    existing = [
        h for h in store_hooks
        if h.get("channel") == "http" and h.get("url", "").rstrip("/") == webhook_url.rstrip("/")
    ]
    if existing:
        print(f"Webhook 已存在: {webhook_url} events={existing[0].get('events')}")
    else:
        # 更新同路径但域名不同的旧 Webhook,避免重复注册
        stale = [
            h for h in store_hooks
            if h.get("channel") == "http"
            and h.get("url", "").rstrip("/").endswith("/api/payment/webhook/waffo-pancake")
        ]
        if stale:
            ok, result = waffo_pancake.update_webhook(stale[0]["id"], url=webhook_url)
            if not ok or result.get("errors"):
                print("更新 Webhook URL 失败:", json.dumps(result, ensure_ascii=False)[:500])
                return 1
            print(f"已更新 Webhook URL: {stale[0]['id']} -> {webhook_url}")
        else:
            ok, result = waffo_pancake.add_webhook(
                url=webhook_url,
                events=["order.completed", "refund.succeeded"],
            )
            if not ok or result.get("errors"):
                print("注册 Webhook 失败:", json.dumps(result, ensure_ascii=False)[:500])
                return 1
            wh = (result.get("data") or {}).get("webhook") or {}
            print(f"已注册 Webhook: {wh.get('id')} -> {webhook_url} events={wh.get('events')} testMode={wh.get('testMode')}")

    # 4. Persist configuration into .env (never overwrite existing keys)
    env_path = ROOT / ".env"
    lines = []
    if env_path.exists():
        lines = env_path.read_text(encoding="utf-8").splitlines()
    keys = {
        "WAFFO_PANCAKE_MERCHANT_ID": waffo_pancake.merchant_id(),
        "WAFFO_PANCAKE_STORE_ID": waffo_pancake.store_id(),
        "WAFFO_PANCAKE_PRIVATE_KEY": os.getenv("WAFFO_PANCAKE_PRIVATE_KEY", ""),
        "WAFFO_PANCAKE_ENV": waffo_pancake.pancake_env(),
        "WAFFO_PANCAKE_PRODUCT_IDS": json.dumps({"pro": product_id}, ensure_ascii=False),
        "WAFFO_PANCAKE_CURRENCY": "CNY",
    }
    existing_keys = {line.split("=", 1)[0].strip() for line in lines if "=" in line and not line.strip().startswith("#")}
    added = []
    for key, value in keys.items():
        if key in existing_keys:
            continue
        lines.append(f"{key}={value}")
        added.append(key)
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"已写入 {env_path} (新增: {', '.join(added) if added else '无'})")

    print("\n完成! 请确认:")
    print(f"  1. 后端环境已有 WAFFO_PANCAKE_MERCHANT_ID / WAFFO_PANCAKE_PRIVATE_KEY / WAFFO_PANCAKE_STORE_ID")
    print(f"  2. 支付回调需公网可达: {webhook_url}")
    print("  3. /pricing 将显示「Waffo 支付」并跳转 Pancake 收银台")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

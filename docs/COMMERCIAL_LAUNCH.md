# 商业化上线清单

面向 **公网 Demo → 付费试点 → 正式收费** 三阶段。与 [COMMERCIAL_DEMO.md](./COMMERCIAL_DEMO.md)（销售演示剧本）配合使用。

## 环境档位

| 档位 | 典型配置 | 用户可见 |
|------|----------|----------|
| **public_demo** | `APP_ENV=production` + `ALLOW_DEMO_ACCOUNTS=true` + `PAYMENT_TEST_MODE=true` | 顶栏琥珀色横幅；定价页可点「支付完成」模拟 |
| **pilot** | 生产密钥已设，仍可能保留 Demo 或测试支付 | `/trust` 显示试点咨询邮箱 |
| **production** | 关 Demo、关测试支付、`PAYMENT_WEBHOOK_SECRET` 已配置 | 仅 Webhook 确认订单；轮询订单状态 |

查询当前档位：`GET /api/commercial/status`（无需登录）或 `GET /api/health`（含 `deploy_profile` / `production_warnings`）。

## 阶段 A — 公网 Demo（简历 / 投融资演示）

参考 `render.yaml` 默认变量即可。

```bash
APP_ENV=production
ALLOW_DEMO_ACCOUNTS=true
PAYMENT_TEST_MODE=true
PUBLIC_DEMO_BASE_URL=https://<your-app>.onrender.com
```

- [ ] `/showcase` 可打开  
- [ ] `demo` / `demo123` 可登录  
- [ ] `/trust` 与定价页显示「演示支付」  
- [ ] README Homepage 指向稳定 URL（勿用临时 Cloudflare 隧道做主链接）

## 阶段 B — 付费试点（1–3 家客户）

复制 `render-production.env.example` 到托管平台环境变量：

```bash
APP_ENV=production
ALLOW_DEMO_ACCOUNTS=false
PAYMENT_TEST_MODE=false
SECRET_KEY=<openssl rand -hex 32>
PAYMENT_WEBHOOK_SECRET=<openssl rand -hex 32>
INITIAL_ADMIN_PASSWORD=<strong-password>
PILOT_CONTACT_EMAIL=you@company.com
```

- [ ] 启动日志无 `[commercial] WARNING`（或仅可接受项）  
- [ ] 客户账号无法使用 `demo` 登录  
- [ ] 支付网关回调指向 `POST https://<host>/api/payment/webhook`  
- [ ] 回调 Body 示例：`{"order_id":"...","payment_status":"paid","transaction_id":"..."}`  
- [ ] 签名头：`X-Payment-Signature` = HMAC-SHA256(raw_body, `PAYMENT_WEBHOOK_SECRET`)  
- [ ] 定价页生成订单后**不显示**「支付完成」，自动轮询订单状态  
- [ ] 持久化：`DATABASE_URL` → Postgres（[POSTGRES.md](./POSTGRES.md)）或 `data/` 卷 SQLite  
- [ ] 运行 `./scripts/seed_demo.sh` 仅用于内部演示账号，非客户租户  

### Webhook 联调（通用 HMAC）

```bash
BODY='{"order_id":"<ORDER_ID>","payment_status":"paid","transaction_id":"test-1"}'
SIG=$(printf '%s' "$BODY" | openssl dgst -sha256 -hmac "$PAYMENT_WEBHOOK_SECRET" | awk '{print $2}')
curl -X POST "https://<host>/api/payment/webhook" \
  -H "Content-Type: application/json" \
  -H "X-Payment-Signature: $SIG" \
  -d "$BODY"
```

### Stripe Checkout 沙箱（推荐海外试点）

1. [Stripe Dashboard](https://dashboard.stripe.com/test/apikeys) 获取 `sk_test_...`
2. Webhooks → Add endpoint → `https://<host>/api/payment/webhook/stripe` → 事件 `checkout.session.completed` → 复制 `whsec_...`
3. 环境变量：

```bash
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
APP_PUBLIC_URL=https://<host>
ALLOW_DEMO_ACCOUNTS=false
PAYMENT_TEST_MODE=false
```

4. 定价页会出现 **银行卡 (Stripe)**；创建订单后跳转 Stripe Checkout，支付成功后自动轮询/回调升级套餐。
5. 测试卡号：`4242 4242 4242 4242`（Stripe 文档）

```bash
pip install 'stripe>=8,<9'
./scripts/validate_production_env.sh
APP_ENV=production ALLOW_DEMO_ACCOUNTS=false PAYMENT_TEST_MODE=false \
  STRIPE_SECRET_KEY=sk_test_xxx STRIPE_WEBHOOK_SECRET=whsec_xxx \
  SECRET_KEY="$(openssl rand -hex 32)" ./scripts/validate_production_env.sh
```

## 阶段 C — 正式收费（仍可为 SQLite 单机）

在阶段 B 基础上增加：

- [ ] 接入真实微信/支付宝（二维码 URL 替换 `create-order` 中的演示 QR）  
- [ ] Postgres 迁移（多租户、备份）— 见架构说明  
- [ ] 隐私政策 / 数据处理协议  
- [ ] 监控：`/api/health` 纳入 Uptime 探测  
- [ ] LLM Key 按客户或按环境配置  

## 页面与 API 索引

| 路径 | 用途 |
|------|------|
| `/trust` | 客户可见：数据来源 + 支付边界 + 当前环境状态 |
| `/pricing` | 套餐 + 订单；随 `payment_mode` 切换 UI |
| `/api/commercial/status` | 前端横幅、作品集 |
| `/api/payment/webhook` | 生产收款确认 |

## 验证命令

```bash
chmod +x scripts/validate_production_env.sh
./scripts/validate_production_env.sh
./scripts/validate_production_env.sh --url https://<your-host>

./scripts/run_tests.sh tests/test_commercial_config.py tests/test_stripe_payment.py -q
./scripts/run_tests.sh tests/test_api_flows.py -q -k payment
curl -s http://127.0.0.1:8080/api/commercial/status | python3 -m json.tool
```

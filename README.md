# Game Analyzer — 游戏数据分析 Web 应用

[![CI](https://github.com/alex-Tesla3/game-analyzer/actions/workflows/ci.yml/badge.svg)](https://github.com/alex-Tesla3/game-analyzer/actions/workflows/ci.yml)

全栈游戏 BI 与竞品情报 POC：从 **Steam / TapTap / Google Play** 公开评论抓取，自动同步运营看板，支持 AI/规则报告、团队归档与商业化演示。

| | |
|---|---|
| **GitHub** | https://github.com/alex-Tesla3/game-analyzer |
| **作品集** | 本地 `/showcase` · [在线 Demo](https://github.com/alex-Tesla3/game-analyzer#live-demo) |
| **演示视频** | [game-analyzer-demo.mp4](docs/demo/game-analyzer-demo.mp4) |
| **简历素材** | [docs/RESUME.md](docs/RESUME.md) |

![数据看板](docs/screenshots/01-dashboard.png)

## 快速启动

```bash
cd game_analyzer
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
./scripts/dev.sh
```

浏览器打开：http://127.0.0.1:8080 （产品首页） · **先抓取**：http://127.0.0.1:8080/guide 或 `/mvp` · 数据看板：http://127.0.0.1:8080/dashboard · **作品集页**：http://127.0.0.1:8080/showcase · 数据流说明：`/trust`

`scripts/dev.sh` 会优先使用本项目 `.venv`，避免误用父目录或系统 Python。直接启动也可以：
`.venv/bin/python -m uvicorn src.web_app:app --host 127.0.0.1 --port 8080 --reload`。

**公网分享：** `./scripts/share_demo.sh` → `cat /tmp/game-analyzer-tunnel.url`（临时链接，需本机在线）

**稳定 Demo：** [Render 一键部署](#render-免费层推荐) · [Railway](docs/DEPLOY.md) · 设置 `PUBLIC_DEMO_BASE_URL` 后 `/showcase` 显示公网横幅

**演示视频：** [docs/demo/game-analyzer-demo.mp4](docs/demo/game-analyzer-demo.mp4) · 重录 `./scripts/record_demo_video.sh`

English README: [README.en.md](README.en.md) · 部署：[docs/DEPLOY.md](docs/DEPLOY.md) · GitHub 同步：[docs/GITHUB_PUBLISH.md](docs/GITHUB_PUBLISH.md) · **简历终稿：[docs/RESUME_PASTE.md](docs/RESUME_PASTE.md)** · 详细素材：[docs/RESUME.md](docs/RESUME.md)

## Render 免费层（推荐稳定 Demo）

1. 打开 [Render Dashboard](https://dashboard.render.com/) → **New** → **Blueprint**  
2. 连接 GitHub 仓库 `alex-Tesla3/game-analyzer`（仓库根目录含 `render.yaml`）  
3. 部署完成后访问 `https://<app-name>.onrender.com/showcase`  
4. 设置环境变量 `PUBLIC_DEMO_BASE_URL=https://<app-name>.onrender.com` 并重启（作品集页显示公网横幅）

Demo 账号：`demo` / `demo123`（`ALLOW_DEMO_ACCOUNTS=true` 已写在 Blueprint 中）

## 默认账号（仅开发）

| 账号 | 密码 | 角色 |
|------|------|------|
| admin | admin123 | 管理员 |
| demo | demo123 | 客户 |
| agent1 | agent123 | 人工坐席 |

生产环境请修改密码并设置 `ALLOW_DEMO_ACCOUNTS=false`。

## 数据流：抓取 → 看板（按用户隔离）

```
登录后：分析向导 /guide  或  MVP /mvp  抓取
        ↓
data/mvp/users/{username}/steam_dataset.json（评论 + 样本指标）
        ↓
运营看板 /dashboard  自动读取该用户目录（/api/metrics）
        ↓
筛选栏「应用筛选」→ KPI / 平台排行 / 预警
```

每位登录用户拥有**独立 MVP 数据集**；未登录访问 `/mvp` 会跳转登录。向导/MVP 侧重深度报告，看板侧重筛选汇总。详见 `/trust` 或看板内「数据流说明」。

## 数据优先级

用户看到的评论/指标按以下顺序解析（见 `src/data_resolution.py`）：

1. **用户导入** CSV（Owner 经营指标，可选）
2. **MVP 抓取真数据**（`data/mvp/users/{username}/`，含 Steam / TapTap / Google Play）
3. **24h 缓存**
4. **无数据** — 看板显示空态并引导先抓取（已不再默认回退 mock）

高级分析 / 实时 WebSocket 在数据不足时会标注 `simulated: true`。

## LLM 与语音

- 管理后台 → LLM 配置：支持 OpenAI / Ollama 等，配置写入 `data/game_analyzer.db`
- Chrome：浏览器原生语音输入
- Cursor 内置浏览器：录音 + 服务端 Whisper（需 OpenAI API Key）

## 在线客服

- 客户：首页 → 帮助中心 → 在线客服（`demo` 账号）
- 坐席：http://127.0.0.1:8080/agent/console（`agent1`）
- 多账号：不同浏览器标签页分别登录（`sessionStorage` 隔离）

## API 限制

- IP 速率限制：默认 60 次/分钟（`config/config.json` → `security.rate_limit`）
- 用户月度 API 配额：按套餐 `api_quota` 计数，管理员/坐席不限
- 试用到期后自动按免费版配额
- **防滥用（中等）**：同 IP/设备限制注册频率；邮箱不可重复注册；每设备仅一次 7 天试用；同设备下免费账号共享月度 API 池（1000 次）

管理员可查关联账号：`GET /api/admin/abuse/linked?token=...&device_id=...` 或 `&ip=...`

## 告警

应用启动后后台每 60 秒检查 `alert_rules` 表中启用的规则，触发时写日志并可 webhook 通知。

## Docker

```bash
cp .env.example .env   # 填写 SECRET_KEY 等
docker compose up -d --build
curl http://localhost:8080/api/health
```

持久化目录：`./data`（SQLite、MVP 产物、导入数据）

## 测试

```bash
chmod +x scripts/run_tests.sh
./scripts/run_tests.sh          # 单元测试（与 CI 一致，自动关闭限流）
pytest tests/ -q                # 等价于上方脚本
```

**分析向导（推荐入口）**：登录后访问 `/guide`，选择 Steam / TapTap / Google Play，抓取后数据自动进入看板。

**MVP 快速抓取**：`/mvp` — 按渠道重新抓取并跳转看板。

**数据说明**：`/trust` — 抓取与看板关系、真数据边界。

**Playwright 浏览器 E2E**（登录 → 看板 → 高级分析 → 竞品工作台 → 资料库）：

```bash
# 推荐：使用本机 Chrome，免下载 Chromium
PLAYWRIGHT_CHANNEL=chrome ./scripts/run_browser_e2e.sh

# 或安装 Playwright 自带 Chromium
./scripts/run_browser_e2e.sh
```

仅跑浏览器用例：`pytest tests/e2e -m browser -v`

**Demo 演示包（离线，无需网络）**：

```bash
./scripts/seed_demo.sh          # 写入 demo MVP + 样例归档
# 对外 Landing：/welcome · 登录后向导：/guide · 落地指导：/work
```

**商业化 POC 剧本**（客户演示 / 销售话术）：见 [docs/COMMERCIAL_DEMO.md](docs/COMMERCIAL_DEMO.md)

## 商业化入口（POC）

| 页面 | 路径 | 用途 |
|------|------|------|
| **产品首页** | `/` | 默认 Landing，一键 Demo |
| MVP 抓取 | `/mvp` | 按渠道重新抓取 → 跳转看板 |
| 数据看板 | `/dashboard` | BI 仪表盘、KPI（读取抓取数据） |
| 分析向导 | `/guide` | 抓取 → 报告 → 归档 → 同步看板 |
| 数据流说明 | `/trust` | 抓取与看板关系、真数据边界 |
| 落地指导 | `/work` | 行动清单、导出、复测进度 |
| 复盘归档 | `/games/review` | 案例库、分享、复测 |
| 团队协作 | `/team` | 成员、共享报告 |
| 订阅套餐 | `/pricing` | 配额展示（演示支付） |

## 模块说明

| 模块 | 状态 |
|------|------|
| 多平台抓取（Steam/TapTap/Google Play） | 可用 |
| 抓取 → 看板自动同步 | 可用 |
| 数据导入 / MVP / 过滤 | 可用 |
| 游戏资料库 + 玩法拆解 | 可用（`/games/library`） |
| 在线客服 + 坐席台 | 可用 |
| LLM 分析 | 需配置 |
| 告警调度 | 已接入后台任务 |
| 支付 | **演示**（Mock 二维码）；可切换 **Waffo Pancake** / **Stripe** 真实收款 |

## 支付配置（可选）

默认 `PAYMENT_TEST_MODE=true` 时为演示支付（Mock 二维码，非真实扣款）。
接入真实收款只需在环境变量中配置任一网关：

- **Waffo Pancake（推荐）**：在 [Waffo Pancake Dashboard](https://pancake.waffo.ai) → API & Development
  创建 API Key 并下载商户私钥，然后设置：

  ```
  WAFFO_PANCAKE_MERCHANT_ID=MER_xxx
  WAFFO_PANCAKE_STORE_ID=STO_xxx
  WAFFO_PANCAKE_PRIVATE_KEY=xxx      # RSA 私钥（base64 DER PKCS#8 或 PEM）
  WAFFO_PANCAKE_ENV=test             # test | prod（webhook 验签公钥按此选择）
  WAFFO_PANCAKE_PRODUCT_IDS={"pro": "PROD_xxx"}
  WAFFO_PANCAKE_CURRENCY=CNY
  ```

  一键配置（验证店铺、创建「专业版」商品、注册 `order.completed` 回调并写入 `.env`）：

  ```bash
  .venv/bin/python scripts/configure_waffo_pancake.py --public-url https://your-app.example.com
  ```

  配置后 `/pricing` 自动出现「Waffo 支付」，下单跳转 Waffo Pancake 收银台；
  支付回调 `POST /api/payment/webhook/waffo-pancake`（`X-Waffo-Signature` RSA-SHA256 验签）确认订单。
  回调地址需公网可达（HTTPS），通过 `APP_PUBLIC_URL` / `PUBLIC_DEMO_BASE_URL` 指定。

- **Waffo Acquiring API（备用）**：`WAFFO_API_KEY` / `WAFFO_PRIVATE_KEY` / `WAFFO_PUBLIC_KEY` /
  `WAFFO_MERCHANT_ID` / `WAFFO_ENV`，回调 `/api/payment/webhook/waffo`。

- **Stripe**：设置 `STRIPE_SECRET_KEY` + `STRIPE_WEBHOOK_SECRET`，`/pricing` 显示银行卡支付。

生产环境（`APP_ENV=production`）请设置 `PAYMENT_TEST_MODE=false` 并配置回调密钥，
否则支付模式会进入 `blocked`。

## 两系统定位

| 系统 | 定位 | 职责 | 数据 |
|---|---|---|---|
| **A · 游戏舆情 AI 分析平台** | 对外内容站 / SEO 获客 | 讲清能力、行业科普、按关键词承接搜索流量 | 不含实时数据，不编造内容 |
| **B · Game Analyzer 数据分析工具** | 数据产品（登录使用） | 抓取公开评论 → 清洗/标签/聚类/看板/报告/预警 | 真实公开数据；经营类指标需业务数据，不可验证功能已下线 |

用户路径：`搜索/内容 → 能力认知(A) → 登录体验(B) → 看板/报告(B)`。详见页面 `/about`。

## AI 数据管道（Agent + Supabase）

对爬取评论做「清洗 → LLM 标签 → Embedding → 聚合」，结果存 Supabase（Postgres + pgvector）：

- `src/services/data_agent.py` — 管道编排（clean / label / embed / store / aggregate 可独立开关、可断点）
- `src/services/noise_detector.py` — 水军/噪音检测：规则（重复/短模板/纯评分/爆发式刷评）+ embedding 相似度 + LLM 复核
- `src/services/review_labeler.py` — LLM 标签（情感/主题/游戏维度/意图），LLM 不可用时自动回退规则
- `src/services/supabase_store.py` — Supabase 数据层（reviews / review_labels / review_embeddings / noise_flags / metrics，pgvector + HNSW + RLS）
- `src/services/llm_client.py` — 新增 `embed_texts()`，支持 OpenAI / Ollama embedding

**API**：

| 接口 | 说明 |
|---|---|
| `POST /api/agent/process` | 对指定数据集跑管道，返回分步统计与聚合 |
| `GET /api/agent/status` | Supabase/embedding/LLM 配置状态、噪音统计 |
| `POST /api/agent/semantic-search` | 语义检索评论（需 Supabase + embedding） |

**配置**：

```bash
# Supabase(连接串含密码,只放本地 .env / Render Secret)
SUPABASE_DATABASE_URL=postgresql://postgres:<password>@db.<ref>.supabase.co:5432/postgres
EMBEDDING_DIM=1536        # OpenAI=1536; Ollama nomic-embed-text=768
EMBEDDING_MODEL=          # 默认按 provider 自动选择
REPORT_EXCLUDE_NOISE=false  # true 时报告/看板自动剔除水军评论
```

**迁移已有数据**：`.venv/bin/python scripts/migrate_to_supabase.py [--embed]`

`REPORT_EXCLUDE_NOISE=true` 后，现有报告/看板在读取评论时会自动跳过 `is_noise=true` 的评论（需先跑过 Agent 管道打标）。

更多 MVP 流水线见 `MVP_README.md`。

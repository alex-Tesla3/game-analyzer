# Game Analyzer — 游戏数据分析 Web 应用

[![CI](https://github.com/alex-Tesla3/game-analyzer/actions/workflows/ci.yml/badge.svg)](https://github.com/alex-Tesla3/game-analyzer/actions/workflows/ci.yml)

本地运行的游戏 BI 仪表盘，支持评论/指标分析、MVP Steam 数据、在线客服、LLM 分析等。

![数据看板](docs/screenshots/01-dashboard.png)

## 快速启动

```bash
cd game_analyzer
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
./scripts/dev.sh
```

浏览器打开：http://127.0.0.1:8080 （产品首页） · 数据看板：http://127.0.0.1:8080/dashboard · **作品集页**：http://127.0.0.1:8080/showcase

`scripts/dev.sh` 会优先使用本项目 `.venv`，避免误用父目录或系统 Python。直接启动也可以：
`.venv/bin/python -m uvicorn src.web_app:app --host 127.0.0.1 --port 8080 --reload`。

**公网分享：** `./scripts/share_demo.sh` → `cat /tmp/game-analyzer-tunnel.url`（临时链接，需本机在线）

**稳定 Demo：** Railway 见 [docs/DEPLOY.md](docs/DEPLOY.md) · 设置 `PUBLIC_DEMO_BASE_URL` 后 `/showcase` 显示公网横幅

**演示视频：** [docs/demo/game-analyzer-demo.mp4](docs/demo/game-analyzer-demo.mp4) · 重录 `./scripts/record_demo_video.sh`

English README: [README.en.md](README.en.md) · 部署：[docs/DEPLOY.md](docs/DEPLOY.md) · **简历素材：[docs/RESUME.md](docs/RESUME.md)** · 发布 GitHub：[docs/GITHUB_PUBLISH.md](docs/GITHUB_PUBLISH.md)

## 默认账号（仅开发）

| 账号 | 密码 | 角色 |
|------|------|------|
| admin | admin123 | 管理员 |
| demo | demo123 | 客户 |
| agent1 | agent123 | 人工坐席 |

生产环境请修改密码并设置 `ALLOW_DEMO_ACCOUNTS=false`。

## 数据优先级

用户看到的评论/指标按以下顺序解析（见 `src/data_resolution.py`）：

1. 用户导入数据
2. MVP Steam 真数据（`data/mvp/`）
3. 缓存
4. `mock_data/` 演示数据

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

**分析向导（推荐入口）**：登录后访问 `/guide`，输入 Steam AppID 一键生成报告与行动清单。

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
| 数据看板 | `/dashboard` | BI 仪表盘、KPI |
| 分析向导 | `/guide` | 抓取 → 报告 → 归档 |
| 落地指导 | `/work` | 行动清单、导出、复测进度 |
| 复盘归档 | `/games/review` | 案例库、分享、复测 |
| 团队协作 | `/team` | 成员、共享报告 |
| 订阅套餐 | `/pricing` | 配额展示（演示支付） |

## 模块说明

| 模块 | 状态 |
|------|------|
| 数据导入 / MVP / 过滤 | 可用 |
| 游戏资料库 + 玩法拆解 | 可用（`/games/library`） |
| 在线客服 + 坐席台 | 可用 |
| LLM 分析 | 需配置 |
| 告警调度 | 已接入后台任务 |
| 支付 | **演示**（Mock 二维码，非真实收款） |
| 平台同步 API | 无密钥时为 **模拟数据** |

更多 MVP 流水线见 `MVP_README.md`。

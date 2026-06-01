# Game Analyzer — 简历素材

> 独立全栈 POC · 游戏 BI + 竞品情报 · 2025–2026  
> 技术栈：Python 3.11 · FastAPI · Pandas · SQLite · Vanilla JS · pytest · Playwright · Docker

## 一句话（中英文）

**中文：** 独立开发的全栈游戏数据分析 SaaS POC，覆盖 Steam/TapTap 公开数据采集、BI 看板、AI/规则混合报告、团队归档与复测闭环，配套 170+ 单元测试与 CI。

**English:** Built a full-stack game analytics SaaS POC (FastAPI + vanilla JS) with multi-platform review ingestion, BI dashboards, LLM/rule hybrid reporting, team collaboration, 170+ pytest cases, and GitHub Actions CI.

## STAR 项目描述（可直接粘贴简历）

### 1. 数据层统一

- **S** — 产品/运营需要从 Steam、TapTap 等多源评论与指标做竞品对比，但导入数据、MVP 快照与 mock 演示数据格式不一致，看板筛选常失效（产品名只显示数字、品类单一）。
- **T** — 设计统一数据目录，让 Dashboard、竞品页、向导共用同一套产品/品类/周期选项。
- **A** — 实现 `data_catalog.py` 合并 metrics、游戏库与 MVP 分析结果；服务端 `/api/metrics` + `metric_matches_period()` 统一 period 别名；前端抽取 `dashboard-filters.js` 模块化筛选逻辑。
- **R** — 看板可正确展示 CS2/Dota2 等真实产品名与多品类；筛选「应用」后 KPI 由服务端重算，避免纯前端 mock 默认值。

### 2. 端到端分析闭环

- **S** — 制作人缺少从「拉评论 → 写报告 → 团队共享 → 复测对比」的一体化工具，Excel 无法 scale。
- **T** — 交付可演示的端到端分析链路，支持公开数据 + 可复现 demo 脚本。
- **A** — 分析向导（Steam AppID / 游戏名）→ 结构化报告 + P0/P1 行动项 → 归档分享 → `/work` 导出；`scripts/seed_demo.sh` 一键注入 CS2/Dota2 案例。
- **R** — 5 分钟可完成完整 demo（见 `docs/CASE_STUDY_CS2_DOTA2.md`）；面试官可本地 `./scripts/run_tests.sh` 验证核心 API。

### 3. 工程化与可部署

- **S** — POC 需要证明不仅是 UI 原型，而是可测试、可部署、可对外演示的工程产物。
- **T** — 建立 CI、健康检查、作品集页与部署文档，支持 Docker / 云部署 / 临时公网隧道。
- **A** — 40+ 测试模块（170+ cases）、Playwright E2E、GHA workflow；`/showcase` 作品集页；`fly.toml` + `docker compose`；`scripts/share_demo.sh` Cloudflare 快速隧道。
- **R** — `./scripts/run_tests.sh` 全绿；`/api/health` 暴露版本与环境；截图与案例文档可直接放 GitHub README。

## 量化指标（面试可引用）

| 指标 | 数值 |
|------|------|
| 后端路由模块 | 17+ FastAPI routers |
| 单元测试 | 170+ cases，40+ 测试文件 |
| 前端模块化 | `dashboard-filters.js`、`app-nav.js`、`analysis-guide.js` |
| 数据源 | 用户 CSV / MVP Steam / mock（带来源标注） |
| 部署方式 | Docker Compose · Fly.io · Cloudflare 隧道 |

最近本地验证（2026-06-01）：`./scripts/run_tests.sh -q` 通过；`PLAYWRIGHT_CHANNEL=chrome ./scripts/run_browser_e2e.sh` 通过 9 个浏览器 E2E；`./scripts/dev.sh` 启动后 `/api/health` 返回 `status: ok`。

## 演示视频

`docs/demo/game-analyzer-demo.mp4`（约 60 秒：showcase → dashboard → 竞品 → 向导 → 团队）

重新录制：`./scripts/record_demo_video.sh`

## 链接（填写后放简历）

| 类型 | URL |
|------|-----|
| Live Demo | `https://<your-domain>/showcase` 或 Cloudflare 隧道 URL |
| GitHub | `https://github.com/<you>/game-analyzer` |
| 案例脚本 | 本地 `./scripts/seed_demo.sh` → `/dashboard` |
| Demo 账号 | `demo` / `demo123`（需 `ALLOW_DEMO_ACCOUNTS=true`） |

## 发布前检查

- `./scripts/run_tests.sh -q` 全绿
- `PLAYWRIGHT_CHANNEL=chrome ./scripts/run_browser_e2e.sh` 全绿
- `./scripts/dev.sh` 启动后 `/api/health` 返回 `status: ok`
- 独立 GitHub 仓库不要包含 `.env`、`.venv/`、`data/game_analyzer.db`、`.DS_Store`、`output.jsonl`
- README 首屏补上 Live Demo / GitHub 链接后再投递

## 演示顺序（3–5 分钟）

1. `/showcase` — 项目概览与架构  
2. `/dashboard` — 产品/品类/周期筛选 + KPI  
3. `/games/compare` — CS2 vs Dota2 六维对比  
4. `/guide` — 分析向导与行动项  
5. `/team` — 归档与协作  

详见 [CASE_STUDY_CS2_DOTA2.md](./CASE_STUDY_CS2_DOTA2.md)、[COMMERCIAL_DEMO.md](./COMMERCIAL_DEMO.md)。

## 诚实边界（面试主动说明）

- 部分 owner 级 KPI 在数据不足时标注 `simulated: true`，公开评论为真实 Steam 样本。
- SQLite 单 worker 适合 POC；多租户生产环境需迁移 Postgres（已在架构文档说明）。
- Cloudflare 快速隧道 URL 临时有效；长期 Demo 建议 Fly.io / Railway 固定域名。

## 截图

运行 `./scripts/capture_screenshots.sh` 后可用：

![Dashboard](./screenshots/01-dashboard.png)

更多：`docs/screenshots/02-guide.png` … `05-showcase.png`

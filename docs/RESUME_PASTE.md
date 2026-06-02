# Game Analyzer — 简历粘贴区（终稿）

> 复制到简历「项目经历」；按岗位保留 2–3 条即可。

## 项目头

**Game Analyzer — 游戏 BI 与竞品情报平台** · 独立全栈 POC · 2025–2026  
GitHub: https://github.com/alex-Tesla3/game-analyzer  
Demo: https://github.com/alex-Tesla3/game-analyzer#快速启动（本地）或仓库 Homepage 公网链接  
技术栈: Python · FastAPI · Pandas · SQLite · Vanilla JS · pytest · Playwright · Docker · GitHub Actions

## 三条精简 Bullet（推荐）

1. **独立开发**全栈游戏数据分析 POC，设计统一数据目录（`data_catalog.py`）与模块化看板筛选（`dashboard-filters.js`），解决多源数据下产品名/品类展示错误与 KPI 筛选失效问题。  
2. 实现 **Steam/TapTap 公开数据 → BI 看板 → 分析向导 → 团队归档** 端到端链路，提供 CS2/Dota2 可复现案例（`seed_demo.sh`）与 `/showcase` 作品集页。  
3. 建立 **170+ pytest + Playwright E2E + GitHub Actions CI** 全绿流水线；Docker/Render/Railway 部署文档，支持 Cloudflare 临时公网演示。

## 英文版（外企 / 英文简历）

**Game Analyzer — Game BI & Competitor Intelligence (POC)** · Solo full-stack · 2025–2026  
https://github.com/alex-Tesla3/game-analyzer

- Built a full-stack game analytics SaaS POC unifying multi-source catalogs and server-side KPI filters (FastAPI + vanilla JS).  
- Delivered scrape-to-report-to-archive workflow with reproducible CS2/Dota2 demo data and portfolio `/showcase` page.  
- Shipped 170+ pytest cases, Playwright E2E, and green GitHub Actions CI; Docker + Render/Railway deploy paths.

## 面试 30 秒口述

「这是一个面向游戏制作人/运营的 BI 与竞品情报 POC。我从数据层统一入手，把用户导入、Steam MVP 和 mock 演示数据合并成一套 catalog，看板和竞品页共用筛选逻辑。产品上是向导生成报告、团队归档、复测对比的闭环。工程上有 170 多个单测、Playwright E2E 和 GitHub CI。定位是 Commercial POC，SQLite 和 mock 指标都有明确标注，不是声称已上线生产。」

## 投递前 30 秒检查

```bash
./scripts/run_tests.sh -q
PLAYWRIGHT_CHANNEL=chrome ./scripts/run_browser_e2e.sh -q
./scripts/polish_github.sh   # Topics + Homepage
```

- [ ] GitHub README 首屏有链接与 CI 绿勾  
- [ ] 简历 Demo 链接可打开（或注明「需预约演示」）  
- [ ] 表述为 **POC / 原型**，不写「已上线生产系统」

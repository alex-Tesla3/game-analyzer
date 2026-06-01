# 发布独立 GitHub 仓库（简历用）

当前代码位于 `Hermes-Agent/game_analyzer/`。为便于 HR/面试官访问，建议推送到**独立公开仓库**。

## 方式 A：新仓库 + subtree（保留 monorepo 历史）

```bash
cd /path/to/Hermes-Agent
git subtree split --prefix=game_analyzer -b game-analyzer-export
git push git@github.com:<you>/game-analyzer.git game-analyzer-export:main
```

## 方式 B：直接复制目录（最快）

已为你导出到本地仓库（如存在可跳过 rsync）：

```bash
# 默认导出路径
cd ~/Projects/game-analyzer
git log -1 --oneline
```

首次导出：

```bash
GITHUB_EXPORT_DIR=~/Projects/game-analyzer ./scripts/publish_github.sh
```

或手动 rsync：

```bash
rsync -a --exclude '.venv' --exclude '__pycache__' --exclude 'data/game_analyzer.db' \
  --exclude '.env' --exclude '.DS_Store' --exclude 'output.jsonl' \
  Hermes-Agent/game_analyzer/ ~/Projects/game-analyzer/
cd ~/Projects/game-analyzer
git init -b main && git add -A && git commit -m "Initial commit"
git remote add origin git@github.com:<you>/game-analyzer.git
git push -u origin main
```

## 方式 C：一键脚本（推荐）

```bash
cd game_analyzer
brew install gh && gh auth login
GITHUB_USER=<your-username> ./scripts/publish_github.sh
```

## 仓库 README 建议结构

1. 首屏：项目一句话 + **Live Demo** 链接 + 截图  
2. Tech stack 表格  
3. Quick start（3 行命令）  
4. 链接：`docs/RESUME.md`、`docs/PROJECT_SHOWCASE.md`  
5. Topics：`fastapi` `game-analytics` `bi-dashboard` `python` `playwright`

独立仓库已内置 `.github/workflows/ci.yml`，包含单元测试与 Playwright E2E；
workflow 使用 SHA-pinned GitHub Actions，适合公开展示工程规范。

## GitHub About 设置

- **Website:** Live Demo URL（`/showcase`）  
- **Description:** Full-stack game BI & competitor intelligence POC  
- **Topics:** 同上  

## 发布前 smoke test

```bash
./scripts/run_tests.sh -q
PLAYWRIGHT_CHANNEL=chrome ./scripts/run_browser_e2e.sh
PORT=8099 ./scripts/dev.sh
curl http://127.0.0.1:8099/api/health
```

期望返回 `{"status":"ok", ...}`。如果 `python3 -m uvicorn ...` 出现
`numpy.dtype size changed`，说明命中了其它虚拟环境；使用 `./scripts/dev.sh`
或 `.venv/bin/python -m uvicorn ...`。

## 部署固定 Demo（推荐）

| 平台 | 说明 |
|------|------|
| Fly.io | `./scripts/deploy_fly.sh`（需绑卡） |
| Railway | 连接 repo，启动命令见 `docs/DEPLOY.md` |
| 临时分享 | `./scripts/share_demo.sh` → 复制 `/tmp/game-analyzer-tunnel.url` |

部署成功后设置环境变量 `PUBLIC_DEMO_BASE_URL=https://your-app.fly.dev`，`/showcase` 会显示公网链接。

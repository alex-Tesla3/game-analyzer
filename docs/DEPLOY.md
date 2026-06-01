# Deploy Game Analyzer

## Prerequisites

- Docker (local smoke test)
- For cloud: [Fly.io](https://fly.io) or [Railway](https://railway.app) account
- `openssl rand -hex 32` for secrets

## 1. Local Docker (production-like)

```bash
cd game_analyzer
cp .env.example .env
# Edit .env — set SECRET_KEY, INITIAL_ADMIN_PASSWORD, PAYMENT_WEBHOOK_SECRET

docker compose up -d --build
curl http://localhost:8080/api/health
```

Demo login works when `ALLOW_DEMO_ACCOUNTS=true` in `.env`.

## 2. Fly.io（需绑定支付方式）

Fly 新账号创建应用前需添加信用卡（可使用免费额度，但仍需验证账单）：
https://fly.io/dashboard/lee_w/billing

```bash
cd game_analyzer
chmod +x scripts/deploy_fly.sh
./scripts/deploy_fly.sh
```

若出现 `We need your payment information to continue`，请先完成账单绑定，或使用下方 **§ 2b 免信用卡方案**。

After deploy, share:

- Showcase: `https://game-analyzer-demo.fly.dev/showcase`
- Dashboard: `https://game-analyzer-demo.fly.dev/dashboard` (login `demo` / `demo123` if demo accounts enabled)

Manual steps (alternative):

```bash
cd game_analyzer
fly auth login
fly apps create game-analyzer-demo   # once
fly volumes create game_analyzer_data --region sin --size 1
fly secrets set SECRET_KEY="$(openssl rand -hex 32)" ...
fly deploy
fly open /showcase
```

## 2b. 免信用卡 — 临时公网 Demo（推荐简历）

本地运行 + Cloudflare Quick Tunnel，几分钟内获得可分享的 HTTPS 链接：

```bash
brew install cloudflared   # 一次性
cd game_analyzer
chmod +x scripts/share_demo.sh
./scripts/share_demo.sh
```

终端会打印类似 `https://xxxx.trycloudflare.com` 的地址，或查看：

```bash
cat /tmp/game-analyzer-tunnel.url
```

分享：

- `https://xxxx.trycloudflare.com/showcase`
- `https://xxxx.trycloudflare.com/dashboard`（demo / demo123）

可选：在运行 uvicorn 的终端设置 `PUBLIC_DEMO_BASE_URL=https://xxxx.trycloudflare.com`，`/showcase` 页会显示公网 Demo 横幅。

隧道关闭后链接失效；适合面试/简历短期展示。长期 Demo 请用 Fly.io / Railway（§2 / §3）。

## 3. Railway

```bash
cd game_analyzer
chmod +x scripts/deploy_railway.sh
./scripts/deploy_railway.sh
```

1. Or manually: New Project → Deploy from GitHub (root directory `game_analyzer`)
2. Add variables from `.env.example` (at minimum `SECRET_KEY`, `APP_ENV=production`)
3. Add volume mount at `/app/data` for SQLite persistence
4. Start command: `uvicorn src.web_app:app --host 0.0.0.0 --port $PORT --workers 1`

Config file: `railway.toml` (Dockerfile build).

## 4. Post-deploy checklist

- [ ] `/api/health` returns `status: ok`
- [ ] `/showcase` loads project overview
- [ ] Login + `/guide` analysis wizard completes
- [ ] `./scripts/seed_demo.sh` run once on the volume (optional offline samples)
- [ ] Set `ALLOW_DEMO_ACCOUNTS=false` for non-demo production

## CI

GitHub Actions workflow: `.github/workflows/game-analyzer-ci.yml` (unit tests + Playwright E2E on `game_analyzer/**` changes).

Local parity:

```bash
./scripts/run_tests.sh
PLAYWRIGHT_CHANNEL=chrome ./scripts/run_browser_e2e.sh
```

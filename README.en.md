# Game Analyzer — Game BI & Competitor Intelligence Platform

[![CI](https://github.com/alex-Tesla3/game-analyzer/actions/workflows/ci.yml/badge.svg)](https://github.com/alex-Tesla3/game-analyzer/actions/workflows/ci.yml)

Full-stack POC for game producers and live-ops teams: scrape public reviews (Steam / TapTap / Google Play), build BI dashboards, generate AI/rule reports, archive and share with teams.

![Dashboard](docs/screenshots/01-dashboard.png)

**Showcase:** `/showcase` · **Resume bullets:** [docs/RESUME.md](docs/RESUME.md) · **Architecture:** [docs/PROJECT_SHOWCASE.md](docs/PROJECT_SHOWCASE.md)

## Live demo

| Method | URL / Command |
|--------|----------------|
| **GitHub** | https://github.com/alex-Tesla3/game-analyzer |
| Local | http://127.0.0.1:8080/showcase |
| Public tunnel | `./scripts/share_demo.sh` → `cat /tmp/game-analyzer-tunnel.url` |
| Stable cloud | [Render](#render-free-tier) · [Railway](docs/DEPLOY.md) · [Fly.io](docs/DEPLOY.md) |
| **Demo video** | [docs/demo/game-analyzer-demo.mp4](docs/demo/game-analyzer-demo.mp4) |

Set `PUBLIC_DEMO_BASE_URL` so `/showcase` shows the public demo banner.

Demo login: `demo` / `demo123`

## Quick start

```bash
cd game_analyzer
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
./scripts/dev.sh
```

`scripts/dev.sh` prefers the project `.venv`, which avoids accidentally using a
parent or system Python. Direct command:
`.venv/bin/python -m uvicorn src.web_app:app --host 127.0.0.1 --port 8080 --reload`.

- Home: http://127.0.0.1:8080  
- Dashboard: http://127.0.0.1:8080/dashboard (crawl first via `/guide` or `/mvp`)  
- MVP crawl: http://127.0.0.1:8080/mvp  
- Data flow docs: http://127.0.0.1:8080/trust  
- Showcase (portfolio): http://127.0.0.1:8080/showcase  

Demo login (development): `demo` / `demo123`

## Data flow (crawl → dashboard)

Crawls from `/guide` or `/mvp` write to `data/mvp/steam_dataset.json`. The dashboard reads the **same dataset** via `/api/metrics` — no separate import step. Filter on `/dashboard` after crawling.

Priority: user CSV import → MVP crawl (Steam/TapTap/Google Play) → cache → empty (mock fallback removed).

## Features

| Module | Description |
|--------|-------------|
| BI Dashboard | KPI from crawled reviews; product/source/period filters |
| Analysis Wizard | Steam / TapTap / Google Play → report → auto-sync dashboard |
| MVP page | Per-channel re-crawl + link to dashboard |
| Competitor Workbench | Six-dimension comparison + AI summary |
| Team Collaboration | Shared archives, member management |
| Commercial POC | Plans, API quotas, demo payment |

## Tech stack

- **Backend:** Python 3.11, FastAPI, Pandas, SQLite  
- **Frontend:** Server HTML + modular JS (`dashboard-filters.js`, `app-nav.js`)  
- **Quality:** pytest, Playwright E2E, GitHub Actions CI  
- **Deploy:** Docker Compose, Fly.io ([docs/DEPLOY.md](docs/DEPLOY.md))

## Tests

```bash
chmod +x scripts/run_tests.sh
./scripts/run_tests.sh                    # unit tests (CI parity)
PLAYWRIGHT_CHANNEL=chrome ./scripts/run_browser_e2e.sh
```

## Production

```bash
cp .env.example .env   # SECRET_KEY, ALLOW_DEMO_ACCOUNTS=false for real prod
docker compose up -d --build
```

See [docs/DEPLOY.md](docs/DEPLOY.md) for Fly.io / Railway.

## Portfolio

- [Resume material (STAR bullets)](docs/RESUME.md) — CN/EN, interview talking points  
- [Project showcase](docs/PROJECT_SHOWCASE.md) — architecture, screenshots  
- [GitHub repo & sync guide](docs/GITHUB_PUBLISH.md) — https://github.com/alex-Tesla3/game-analyzer  
- [Case study: CS vs Dota 2](docs/CASE_STUDY_CS2_DOTA2.md) — demo script  
- [Commercial demo script](docs/COMMERCIAL_DEMO.md) — 5-minute walkthrough  

Chinese README: [README.md](README.md)

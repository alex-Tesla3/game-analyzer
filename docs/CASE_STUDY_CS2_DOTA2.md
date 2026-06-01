# Case Study: Counter-Strike vs Dota 2 (Steam Public Reviews)

Reproducible sample used in demos and portfolio narratives.

## Setup

```bash
cd game_analyzer
source .venv/bin/activate
./scripts/seed_demo.sh
uvicorn src.web_app:app --host 127.0.0.1 --port 8080 --reload
```

Login: `demo` / `demo123`

## Demo flow (5 min)

| Step | URL | What to show |
|------|-----|--------------|
| 1 | `/dashboard` | Products **Counter-Strike** (730) & **Dota 2** (570); genre filter FPS/MOBA |
| 2 | `/games/compare` | Side-by-side six-dimension competitor scores |
| 3 | `/guide` | Re-run analysis on AppID `730,570` |
| 4 | `/games/review` | Archived report + share link |
| 5 | `/work` | P0/P1 action items exported to CSV |

## Data basis

| Field | Value |
|-------|-------|
| Source | Steam public review samples (`steam_public`) |
| Products | AppID 10 (CS legacy), 730 (CS2), 570 (Dota 2) |
| Trust | Real public comments; KPI funnel may show `simulated: true` when owner metrics absent |

## Talking points (interview)

1. **Problem** — Producers need competitor sentiment without a data team; spreadsheets don't scale across Steam/TapTap.
2. **Approach** — Unified catalog merges library + MVP + user metrics; filters hit `/api/metrics` with server-side validation.
3. **Trade-off** — SQLite + single worker for POC simplicity; documented path to Postgres for multi-tenant scale.
4. **Outcome** — End-to-end loop: scrape → report → archive → team share → retest delta.

## Verify programmatically

```bash
./scripts/run_tests.sh tests/test_data_catalog.py tests/test_filter_records.py -q
curl -s http://127.0.0.1:8080/api/health | python3 -m json.tool
```

Expected health fields: `status`, `version`, `environment`, `demo_accounts_enabled`.

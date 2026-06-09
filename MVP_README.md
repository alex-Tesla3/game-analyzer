# Game Analyzer MVP

Multi-platform crawl pipeline: public reviews → normalized schema → analysis → dashboard sync.

## Platforms

| Channel | CLI / API | Notes |
|---------|-----------|-------|
| Steam | `run_mvp.py --app-ids 730,570` | No API key; public store + reviews |
| TapTap | `GET /api/mvp/taptap?app_ids=168332` | TapTap `webapiv2` + `X-UA` |
| Google Play | `GET /api/mvp/google-play?app_ids=com.example.app` | `google-play-scraper` |

## CLI (Steam batch)

```bash
python3 run_mvp.py --app-ids 730,570,117247 --max-reviews 50
```

## Artifacts (`data/mvp/`)

- `steam_dataset.json` — comments + sample metrics (all channels write here)
- `analysis.json`
- `validation.json`

## FastAPI endpoints

```text
GET /api/mvp/steam?app_ids=730,570&max_reviews=25
GET /api/mvp/taptap?app_ids=168332&max_reviews=25
GET /api/mvp/google-play?app_ids=com.miHoYo.GenshinImpact&max_reviews=25
GET /api/mvp/latest
GET /mvp
```

UI: `/mvp` — per-channel re-crawl buttons + link to `/dashboard`.

## Dashboard sync

Crawls write to `data/mvp/steam_dataset.json`. The dashboard reads the **same file** via `/api/metrics` — no separate import. See `/trust` or the in-dashboard data-flow guide.

Priority (`src/data_resolution.py`):

1. User CSV import (owner metrics)
2. MVP crawl artifacts (Steam / TapTap / Google Play)
3. 24h cache
4. Empty — dashboard shows crawl-first guidance (mock fallback removed)

When MVP artifacts exist, these APIs prefer real crawled data:

- `GET /api/report` — rule-based analysis
- `GET /api/ai_analysis` — grounded `ai_strategy` from MVP run
- `GET /api/comments` and `GET /api/metrics` — `source: mvp_steam` / `mvp_multi`

Demo-only advanced analytics endpoints include `"simulated": true` in responses.

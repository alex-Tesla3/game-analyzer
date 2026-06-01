# Game Analyzer MVP

This MVP creates a real-data analysis loop:

1. Crawl public Steam store data and recent reviews without API keys.
2. Normalize reviews into the existing comments schema and metrics into the existing KPI schema.
3. Generate deterministic product analysis.
4. Recompute source counts and rates to validate that the analysis matches the crawled data.

Run it from the project root:

```bash
python3 run_mvp.py --app-ids 730,570,117247 --max-reviews 50
```

Artifacts are written to `data/mvp/`:

- `steam_dataset.json`
- `analysis.json`
- `validation.json`

The FastAPI app also exposes:

```text
GET /api/mvp/steam?app_ids=730,570&max_reviews=25
GET /api/mvp/latest
GET /mvp
```

When validated MVP artifacts exist under `data/mvp/`, these APIs prefer real Steam data
over mock fixtures (unless the user has imported their own dataset):

- `GET /api/report` — rule-based MVP analysis when validation passed
- `GET /api/ai_analysis` — returns grounded `ai_strategy` from the MVP run
- `GET /api/comments` and `GET /api/metrics` — expose `source: mvp_steam`

Demo-only advanced analytics endpoints include `"simulated": true` in responses.

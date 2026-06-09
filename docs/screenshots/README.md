# Portfolio Screenshots

Add PNG captures here for resume / README / `/showcase`.

| File | Page | What to show |
|------|------|----------------|
| `01-dashboard.png` | `/dashboard` | Product/source filter, KPI cards (after crawl) |
| `02-guide.png` | `/guide` or `/mvp` | Multi-platform crawl + analysis wizard |
| `03-compare.png` | `/games/compare` | Competitor six-dimension comparison |
| `04-team.png` | `/team` | Team list or shared archives |
| `05-showcase.png` | `/showcase` | Portfolio overview page |

## Capture locally

```bash
cd game_analyzer
./scripts/dev.sh   # or uvicorn in another terminal
# Option A: ./scripts/seed_demo.sh  (offline CS2/Dota2)
# Option B: crawl via /mvp or /guide (Steam / TapTap / Google Play) then open /dashboard
./scripts/capture_screenshots.sh
```

Login: `demo` / `demo123`

## Use in docs

Link from `docs/PROJECT_SHOWCASE.md`:

```markdown
![Dashboard](./screenshots/01-dashboard.png)
```

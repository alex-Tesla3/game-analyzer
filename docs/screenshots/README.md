# Portfolio Screenshots

Add PNG captures here for resume / README / `/showcase`.

| File | Page | What to show |
|------|------|----------------|
| `01-dashboard.png` | `/dashboard` | Product filter, genre list, KPI cards |
| `02-guide.png` | `/guide` | Completed analysis wizard + action list |
| `03-compare.png` | `/games/compare` | Competitor six-dimension comparison |
| `04-team.png` | `/team` | Team list or shared archives |
| `05-showcase.png` | `/showcase` | Portfolio overview page |

## Capture locally

```bash
cd game_analyzer
./scripts/seed_demo.sh
PYTHONPATH=src:. uvicorn src.web_app:app --host 127.0.0.1 --port 8080 --reload
./scripts/capture_screenshots.sh
```

Login: `demo` / `demo123`

## Use in docs

Link from `docs/PROJECT_SHOWCASE.md`:

```markdown
![Dashboard](./screenshots/01-dashboard.png)
```

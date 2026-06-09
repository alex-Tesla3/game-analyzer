# Demo video

~60 second portfolio walkthrough recorded with Playwright.

| File | Use |
|------|-----|
| `game-analyzer-demo.webm` | GitHub README / embed |
| `game-analyzer-demo.mp4` | LinkedIn / 简历附件 |

## Re-record

```bash
cd game_analyzer
./scripts/dev.sh   # or uvicorn in another terminal
```

Option A — offline CS2/Dota2 samples:

```bash
./scripts/seed_demo.sh
./scripts/record_demo_video.sh
```

Option B — live multi-platform crawl (recommended for portfolio):

1. Login `demo` / `demo123`
2. Visit `/mvp` or `/guide` — crawl Steam / TapTap / Google Play
3. Open `/dashboard` and apply filters to show synced data
4. `./scripts/record_demo_video.sh`

```bash
ffmpeg -y -i docs/demo/game-analyzer-demo.webm -c:v libx264 -pix_fmt yuv420p docs/demo/game-analyzer-demo.mp4
```

Server must be on http://127.0.0.1:8080

## README embed (GitHub)

```markdown
https://github.com/alex-Tesla3/game-analyzer/assets/.../game-analyzer-demo.mp4
```

Upload via GitHub release or drag into README editor.

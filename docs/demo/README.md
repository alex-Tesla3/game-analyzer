# Demo video

~60 second portfolio walkthrough recorded with Playwright.

| File | Use |
|------|-----|
| `game-analyzer-demo.webm` | GitHub README / embed |
| `game-analyzer-demo.mp4` | LinkedIn / 简历附件 |

## Re-record

```bash
cd game_analyzer
./scripts/seed_demo.sh
./scripts/record_demo_video.sh
ffmpeg -y -i docs/demo/game-analyzer-demo.webm -c:v libx264 -pix_fmt yuv420p docs/demo/game-analyzer-demo.mp4
```

Server must be on http://127.0.0.1:8080 · login `demo` / `demo123`

## README embed (GitHub)

```markdown
https://github.com/<you>/game-analyzer/assets/.../game-analyzer-demo.mp4
```

Upload via GitHub release or drag into README editor.

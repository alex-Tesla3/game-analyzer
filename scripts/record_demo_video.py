#!/usr/bin/env python3
"""Record a ~60s portfolio demo video via Playwright (server on :8080)."""

from __future__ import annotations

import sys
import time
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("Install: pip install playwright && playwright install chromium")
    sys.exit(1)

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "docs" / "demo"
BASE = "http://127.0.0.1:8080"

STEPS = [
    ("/showcase", 4000, "Portfolio overview"),
    ("/dashboard", 5000, "BI dashboard"),
    ("/games/compare", 5000, "Competitor compare"),
    ("/guide", 5000, "Analysis wizard"),
    ("/team", 4000, "Team collaboration"),
]


def login(page) -> None:
    page.goto(f"{BASE}/login?redirect=%2Fdashboard", wait_until="domcontentloaded")
    page.fill('input[name="username"], #username, input[type="text"]', "demo")
    page.fill('input[name="password"], #password, input[type="password"]', "demo123")
    page.click('button[type="submit"], input[type="submit"], .btn-primary')
    page.wait_for_timeout(1500)


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            locale="zh-CN",
            record_video_dir=str(OUT_DIR),
            record_video_size={"width": 1440, "height": 900},
        )
        page = context.new_page()
        login(page)
        for path, pause_ms, label in STEPS:
            print(f"Recording: {label} ({path})")
            page.goto(f"{BASE}{path}", wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(pause_ms)

        video_path = page.video.path() if page.video else None
        context.close()
        browser.close()

    if not video_path:
        print("No video captured.")
        return 1

    src = Path(video_path)
    dest = OUT_DIR / "game-analyzer-demo.webm"
    if dest.exists():
        dest.unlink()
    src.rename(dest)
    print(f"Saved {dest.relative_to(ROOT)}")
    print("Tip: convert to mp4 for LinkedIn: ffmpeg -i docs/demo/game-analyzer-demo.webm docs/demo/game-analyzer-demo.mp4")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

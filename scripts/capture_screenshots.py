#!/usr/bin/env python3
"""Capture portfolio screenshots via Playwright (requires local server on :8080)."""

from __future__ import annotations

import sys
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("Install playwright: pip install playwright && playwright install chromium")
    sys.exit(1)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "screenshots"
BASE = "http://127.0.0.1:8080"

PAGES = [
    ("01-dashboard.png", "/dashboard", True),
    ("02-guide.png", "/guide", True),
    ("03-compare.png", "/games/compare", True),
    ("04-team.png", "/team", True),
    ("05-showcase.png", "/showcase", False),
]


def login(page) -> None:
    page.goto(f"{BASE}/login?redirect=%2Fdashboard")
    page.fill('input[name="username"], #username, input[type="text"]', "demo")
    page.fill('input[name="password"], #password, input[type="password"]', "demo123")
    page.click('button[type="submit"], input[type="submit"], .btn-primary')
    page.wait_for_timeout(1500)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN")
        page = context.new_page()
        logged_in = False
        for filename, path, needs_auth in PAGES:
            if needs_auth and not logged_in:
                login(page)
                logged_in = True
            url = f"{BASE}{path}"
            page.goto(url, wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(2000)
            dest = OUT / filename
            page.screenshot(path=str(dest), full_page=True)
            print(f"Saved {dest.relative_to(ROOT)}")
        browser.close()
    static_dir = ROOT / "src" / "static" / "img" / "showcase"
    static_dir.mkdir(parents=True, exist_ok=True)
    for png in OUT.glob("*.png"):
        target = static_dir / png.name
        target.write_bytes(png.read_bytes())
        print(f"Copied to {target.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

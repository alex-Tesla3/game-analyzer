"""Shared helpers for Playwright browser E2E tests."""

from __future__ import annotations

import re
from typing import Optional

from playwright.sync_api import Page, expect

DEMO_USER = "demo"
DEMO_PASSWORD = "demo123"


def dismiss_onboarding(page: Page) -> None:
    """Skip first-run onboarding wizard via localStorage."""
    page.add_init_script(
        """
        try {
            localStorage.setItem('ga_onboarding_done_v1', '1');
        } catch (e) {}
        """
    )


def clear_auth_state(page: Page) -> None:
    """Ensure a clean session (Playwright reuses context across tests)."""
    page.evaluate(
        """() => {
            try { localStorage.clear(); sessionStorage.clear(); } catch (e) {}
        }"""
    )


def login(
    page: Page,
    *,
    username: str = DEMO_USER,
    password: str = DEMO_PASSWORD,
    redirect_path: Optional[str] = None,
) -> None:
    dismiss_onboarding(page)
    target = "/login"
    if redirect_path:
        target = f"/login?redirect={redirect_path}"
    page.goto(target)
    page.locator("#username").fill(username)
    page.locator("#password").fill(password)
    page.locator("#login-form button[type='submit']").click()
    page.wait_for_url(re.compile(r"^(?!.*/login).*$"), timeout=20_000)
    expect(page.locator("#username")).to_have_count(0)


def wait_wizard_complete(page: Page, *, timeout_ms: int = 120_000) -> None:
    """Analysis wizard finished with success status and report visible."""
    if "/login" in page.url:
        raise AssertionError(f"Session expired or auth failed — still on login: {page.url}")
    expect(page.locator("#status")).to_contain_text(
        re.compile(r"✅|完成"), timeout=timeout_ms
    )
    expect(page.locator("#report-card")).to_be_visible(timeout=10_000)


def run_guide_demo(page: Page) -> None:
    """Login and auto-run the CS2/Dota2 demo wizard (skip crawl)."""
    login(page, redirect_path="/guide?demo=1&autorun=1")
    page.wait_for_url(re.compile(r"/guide"), timeout=20_000)
    wait_wizard_complete(page)


def wait_dashboard_ready(page: Page) -> None:
    """Dashboard KPI grid populated after loadData()."""
    expect(page.locator("#kpi-grid")).to_be_visible(timeout=20_000)
    page.wait_for_function(
        """() => {
            const grid = document.getElementById('kpi-grid');
            if (!grid) return false;
            const values = grid.querySelectorAll('.kpi-value');
            if (!values.length) return false;
            return Array.from(values).some(el => {
                const t = (el.textContent || '').trim();
                return t && t !== '--' && t !== '—';
            });
        }""",
        timeout=25_000,
    )

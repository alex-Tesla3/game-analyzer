"""Shared pytest fixtures and hermetic test environment."""

from __future__ import annotations

import os

import pytest


@pytest.fixture(scope="session", autouse=True)
def _hermetic_test_env() -> None:
    """Disable rate limits and use isolated flags for API tests."""
    os.environ.setdefault("GA_E2E_DISABLE_RATE_LIMIT", "1")
    os.environ.setdefault("APP_ENV", "development")
    os.environ.setdefault("ALLOW_DEMO_ACCOUNTS", "true")


@pytest.fixture(autouse=True)
def _reset_abuse_event_tables() -> None:
    """Prevent IP/device registration limits from leaking across tests (shared SQLite)."""
    from database import db_manager

    for table in (
        "registration_events",
        "device_trial_claims",
        "device_accounts",
        "login_events",
    ):
        try:
            db_manager.execute(f"DELETE FROM {table}")
        except Exception:
            pass
    yield

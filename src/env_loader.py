"""Dependency-free .env loader (KEY=VALUE lines, minimal parsing)."""

from __future__ import annotations

import os
from pathlib import Path


def _running_under_pytest() -> bool:
    return bool(os.getenv("PYTEST_CURRENT_TEST") or os.getenv("GA_E2E_DISABLE_RATE_LIMIT"))


def load_env_file(path: str = ".env") -> None:
    """Load KEY=VALUE pairs from path into os.environ (never overwrite).

    Skipped while running the test suite so tests stay hermetic and are not
    influenced by a developer's local .env credentials.
    """
    if _running_under_pytest():
        return
    env_path = Path(path)
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value

"""Playwright E2E fixtures: live uvicorn server + browser base URL."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture(scope="session")
def e2e_base_url() -> str:
    """Start uvicorn on an ephemeral port for the browser test session."""
    port = _free_port()
    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT / "src")
    env["GA_E2E_DISABLE_LLM"] = "1"
    env["GA_E2E_DISABLE_RATE_LIMIT"] = "1"

    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "src.web_app:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=str(PROJECT_ROOT),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    base = f"http://127.0.0.1:{port}"
    deadline = time.time() + 45
    last_err: Exception | None = None

    try:
        while time.time() < deadline:
            if proc.poll() is not None:
                err = proc.stderr.read().decode(errors="replace") if proc.stderr else ""
                pytest.fail(f"E2E uvicorn exited early:\n{err}")

            try:
                resp = httpx.get(f"{base}/api/health", timeout=1.5)
                if resp.status_code == 200:
                    from src.services.game_intel import seed_default_library

                    seed_default_library()
                    yield base
                    return
            except Exception as exc:  # noqa: BLE001 — poll until ready
                last_err = exc
            time.sleep(0.25)

        proc.kill()
        pytest.fail(f"E2E server not ready at {base}: {last_err}")
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                proc.kill()


@pytest.fixture(scope="session")
def browser_type_launch_args() -> dict:
    args: dict = {"headless": True}
    channel = os.environ.get("PLAYWRIGHT_CHANNEL", "").strip()
    if channel:
        args["channel"] = channel
    return args


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args, e2e_base_url: str) -> dict:
    return {
        **browser_context_args,
        "base_url": e2e_base_url,
        "locale": "zh-CN",
        "viewport": {"width": 1440, "height": 900},
    }

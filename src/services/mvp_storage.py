"""Per-user MVP artifact directories for multi-tenant crawl isolation."""

from __future__ import annotations

import os
import re
from typing import Optional

from src.mvp_pipeline import DEFAULT_OUTPUT_DIR

_USERNAME_SAFE = re.compile(r"[^\w.-]+")


def safe_username(username: str) -> str:
    token = _USERNAME_SAFE.sub("_", (username or "").strip().lower())
    return token or "anonymous"


def user_mvp_output_dir(username: str) -> str:
    return os.path.abspath(
        os.path.join(DEFAULT_OUTPUT_DIR, "users", safe_username(username))
    )


def resolve_mvp_output_dir(username: Optional[str] = None) -> str:
    if username:
        path = user_mvp_output_dir(username)
        os.makedirs(path, exist_ok=True)
        return path
    return os.path.abspath(DEFAULT_OUTPUT_DIR)

"""Shared helpers for TapTap / Google Play public crawlers."""

from __future__ import annotations

import os
import uuid
from typing import Any, Dict, Optional


def allow_demo_fallback() -> bool:
    return os.getenv("GA_PLATFORM_DEMO_FALLBACK", "false").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def taptap_xua() -> str:
    """Client fingerprint required by TapTap webapiv2."""
    uid = os.getenv("TAPTAP_XUA_UID", "").strip() or str(uuid.uuid4())
    return (
        "V=1&PN=WebApp&LANG=zh_CN&VN_CODE=102&VN=0.1.0&LOC=CN&PLT=PC"
        f"&DS=Android&UID={uid}&DT=PC"
    )


def taptap_params(extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    params = {"X-UA": taptap_xua()}
    if extra:
        params.update(extra)
    return params


def extract_taptap_app_id(token: str) -> Optional[str]:
    """Parse TapTap app id from raw token or URL."""
    raw = (token or "").strip()
    if not raw:
        return None
    for needle in ("/app/", "app_id=", "taptap.cn/app/"):
        if needle in raw:
            tail = raw.split(needle, 1)[1]
            digits = "".join(ch for ch in tail if ch.isdigit())
            if digits:
                return digits
    bare = raw.replace("taptap_", "", 1)
    if bare.isdigit():
        return bare
    return None


def parse_taptap_review_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize TapTap list-by-app moment payload to a flat review dict."""
    moment = row.get("moment") or row
    review = moment.get("review") or row.get("review") or row
    contents = review.get("contents") or {}
    text = ""
    if isinstance(contents, dict):
        text = contents.get("text") or contents.get("raw_text") or ""
    text = text or review.get("content") or review.get("text") or ""
    score = review.get("score") or review.get("rating") or moment.get("score") or 0
    voted_up = review.get("voted_up") if "voted_up" in review else int(score or 0) >= 4
    created_time = (
        moment.get("created_time")
        or moment.get("updated_time")
        or review.get("created_time")
        or review.get("updated_time")
        or row.get("created_time")
    )
    return {
        "score": score,
        "content": text,
        "text": text,
        "voted_up": voted_up,
        "contents": {"text": text},
        "created_time": created_time,
    }

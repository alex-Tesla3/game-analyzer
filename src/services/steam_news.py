"""Fetch Steam news / patch notes for version history import."""

from __future__ import annotations

import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests

STEAM_NEWS_URL = "https://api.steampowered.com/ISteamNews/GetNewsForApp/v0002/"
_VERSION_RE = re.compile(r"\b(v?\d+\.\d+(?:\.\d+)?)\b", re.I)


def fetch_steam_news_items(app_id: str, *, count: int = 10, timeout: int = 12) -> List[Dict[str, Any]]:
    """Return normalized Steam news rows for an app id."""
    app_id = str(app_id or "").strip()
    if not app_id:
        return []

    params: Dict[str, Any] = {"appid": app_id, "count": max(1, min(count, 20)), "format": "json"}
    api_key = os.getenv("STEAM_API_KEY", "").strip()
    if api_key:
        params["key"] = api_key

    try:
        response = requests.get(STEAM_NEWS_URL, params=params, timeout=timeout)
        response.raise_for_status()
        payload = response.json()
    except Exception:
        return []

    items = payload.get("appnews", {}).get("newsitems") or payload.get("appnews", {}).get("news_items") or []
    rows: List[Dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        title = (item.get("title") or "").strip()
        if not title:
            continue
        ts = item.get("date") or item.get("feedlabel") or item.get("feedname")
        released_at = ""
        if isinstance(ts, (int, float)):
            released_at = datetime.utcfromtimestamp(int(ts)).strftime("%Y-%m-%d")
        elif isinstance(ts, str) and ts[:4].isdigit():
            released_at = ts[:10]

        body = (item.get("contents") or item.get("body") or "").strip()
        if body:
            body = re.sub(r"<[^>]+>", " ", body)
            body = re.sub(r"\s+", " ", body)[:500]

        version_label = title
        match = _VERSION_RE.search(title)
        if match:
            version_label = match.group(1)

        rows.append(
            {
                "version_label": version_label[:120],
                "released_at": released_at,
                "change_summary": body or title,
                "change_type": _classify_news(title, body),
                "source": "steam_news",
                "external_url": item.get("url") or "",
                "news_gid": str(item.get("gid") or item.get("id") or ""),
            }
        )
    return rows


def _classify_news(title: str, body: str) -> str:
    text = f"{title} {body}".lower()
    if any(k in text for k in ("balance", "平衡", "nerf", "buff")):
        return "balance"
    if any(k in text for k in ("patch", "hotfix", "fix", "修复", "补丁")):
        return "patch"
    if any(k in text for k in ("update", "更新", "season", "dlc", "content")):
        return "content"
    if any(k in text for k in ("major", "launch", "release", "正式", "大版本")):
        return "major"
    return "minor"

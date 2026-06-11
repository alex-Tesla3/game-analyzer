"""Canonical crawl products: platform IDs, aliases, and custom display names."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Sequence

# Each entry: custom display_name + per-platform IDs + search aliases.
PRODUCT_ENTRIES: List[Dict[str, Any]] = [
    {
        "key": "last_war",
        "display_name": "Last War: Survival",
        "genre": "SLG",
        "aliases": [
            "last war",
            "last war survival",
            "last war: survival",
            "last war生存",
            "last war 生存",
        ],
        "platforms": {
            "google_play": "com.fun.lastwar.gp",
            "taptap": "33569155",
        },
    },
    {
        "key": "dark_war",
        "display_name": "Dark War: Survival",
        "genre": "SLG",
        "aliases": [
            "dark war",
            "dark war survival",
            "dark war: survival",
            "dark war生存",
            "暗黑战争",
        ],
        "platforms": {
            "google_play": "com.readygo.dark.gp",
        },
    },
    {
        "key": "honor_of_kings",
        "display_name": "王者荣耀",
        "genre": "MOBA",
        "aliases": ["王者荣耀", "honor of kings"],
        "platforms": {
            "taptap": "23167",
            "google_play": "com.levelinfinite.sgameGlobal",
        },
        "platform_display_names": {
            "google_play": "王者荣耀国际服",
        },
    },
    {
        "key": "genshin",
        "display_name": "原神",
        "genre": "RPG",
        "aliases": ["原神", "genshin", "genshin impact"],
        "platforms": {
            "taptap": "168332",
            "google_play": "com.miHoYo.GenshinImpact",
        },
    },
]

_PLATFORM_KEYS = {
    "steam": "steam",
    "taptap": "taptap",
    "google_play": "google_play",
    "google play": "google_play",
}


def _norm_platform(platform: str) -> str:
    return _PLATFORM_KEYS.get((platform or "").strip().lower(), (platform or "").strip().lower())


def _build_indexes() -> tuple[
    Dict[str, str],
    Dict[str, Dict[str, str]],
    Dict[str, str],
    Dict[str, str],
    Dict[str, str],
    Dict[str, str],
]:
    """Return id->display, id->genre, taptap aliases/demo, gplay aliases/demo."""
    display_by_id: Dict[str, str] = {}
    genre_by_id: Dict[str, str] = {}
    platform_display: Dict[str, Dict[str, str]] = {}
    taptap_aliases: Dict[str, str] = {}
    taptap_demo: Dict[str, str] = {}
    gplay_aliases: Dict[str, str] = {}
    gplay_demo: Dict[str, str] = {}

    for entry in PRODUCT_ENTRIES:
        base_name = str(entry.get("display_name") or entry.get("key") or "").strip()
        genre = str(entry.get("genre") or "").strip()
        per_platform_names = entry.get("platform_display_names") or {}
        platforms = entry.get("platforms") or {}

        for plat, product_id in platforms.items():
            pid = str(product_id).strip()
            if not pid:
                continue
            name = str(per_platform_names.get(plat) or base_name).strip() or pid
            display_by_id[pid] = name
            if genre:
                genre_by_id[pid] = genre
            platform_display.setdefault(pid, {})[plat] = name

            if plat == "taptap":
                taptap_demo[pid] = name
            elif plat == "google_play":
                gplay_demo[pid] = name

        for alias in entry.get("aliases") or []:
            token = str(alias).strip().lower()
            if not token:
                continue
            for plat, product_id in platforms.items():
                pid = str(product_id).strip()
                if not pid:
                    continue
                if plat == "taptap":
                    taptap_aliases[token] = pid
                elif plat == "google_play":
                    gplay_aliases[token] = pid

    return display_by_id, genre_by_id, platform_display, taptap_aliases, taptap_demo, gplay_aliases, gplay_demo


(
    _DISPLAY_BY_ID,
    _GENRE_BY_ID,
    _PLATFORM_DISPLAY,
    _TAPTAP_ALIASES,
    _TAPTAP_DEMO,
    _GPLAY_ALIASES,
    _GPLAY_DEMO,
) = _build_indexes()


def taptap_alias_map() -> Dict[str, str]:
    return dict(_TAPTAP_ALIASES)


def taptap_demo_map() -> Dict[str, str]:
    return dict(_TAPTAP_DEMO)


def google_play_alias_map() -> Dict[str, str]:
    return dict(_GPLAY_ALIASES)


def google_play_demo_map() -> Dict[str, str]:
    return dict(_GPLAY_DEMO)


def lookup_display_name(
    product_id: str,
    *,
    platform: str = "",
    store_title: str = "",
    overrides: Optional[Dict[str, str]] = None,
) -> str:
    """Resolve friendly product label: override > registry > store title > raw id."""
    pid = str(product_id or "").strip()
    if not pid:
        return store_title or ""

    if overrides and pid in overrides:
        custom = str(overrides[pid]).strip()
        if custom:
            return custom

    plat = _norm_platform(platform)
    if plat and _PLATFORM_DISPLAY.get(pid, {}).get(plat):
        return _PLATFORM_DISPLAY[pid][plat]
    if pid in _DISPLAY_BY_ID:
        return _DISPLAY_BY_ID[pid]

    store = str(store_title or "").strip()
    if store and store != pid:
        return store
    return pid


def lookup_product_genre(product_id: str) -> str:
    return _GENRE_BY_ID.get(str(product_id or "").strip(), "")


def get_mvp_presets() -> List[Dict[str, str]]:
    """Preset picker rows for /api/mvp/catalog (non-Steam mobile titles)."""
    presets: List[Dict[str, str]] = []
    seen: set[str] = set()
    for entry in PRODUCT_ENTRIES:
        genre = str(entry.get("genre") or "")
        platforms = entry.get("platforms") or {}
        per_platform_names = entry.get("platform_display_names") or {}
        base_name = str(entry.get("display_name") or "")
        for plat, product_id in platforms.items():
            if plat not in ("taptap", "google_play"):
                continue
            pid = str(product_id).strip()
            if not pid or pid in seen:
                continue
            name = str(per_platform_names.get(plat) or base_name or pid)
            presets.append(
                {
                    "id": pid,
                    "name": name,
                    "genre": genre,
                    "platform": plat,
                }
            )
            seen.add(pid)
    return presets


def _looks_like_product_id(token: str) -> bool:
    raw = (token or "").strip()
    if not raw:
        return False
    if raw.isdigit():
        return True
    return bool(re.match(r"^[a-zA-Z][a-zA-Z0-9_]*(\.[a-zA-Z][a-zA-Z0-9_]*)+$", raw))


def has_mapping_syntax(raw: str) -> bool:
    return bool(re.search(r"[:@|]", (raw or "").strip()))


def parse_product_name_overrides(raw: str) -> Dict[str, str]:
    """
    Parse custom display names for crawled products.

    Formats:
      - ``product_id:显示名`` (comma / semicolon / newline separated)
      - ``显示名@product_id`` or ``显示名|product_id``
    """
    text = (raw or "").strip()
    if not text:
        return {}

    overrides: Dict[str, str] = {}
    for segment in re.split(r"[\n,;]+", text):
        token = segment.strip()
        if not token:
            continue
        if ":" in token:
            pid, name = token.split(":", 1)
            pid, name = pid.strip(), name.strip()
            if pid and name:
                overrides[pid] = name
            continue
        for sep in ("@", "|"):
            if sep in token:
                left, right = token.split(sep, 1)
                left, right = left.strip(), right.strip()
                if not left or not right:
                    break
                if _looks_like_product_id(left):
                    overrides[left] = right
                else:
                    overrides[right] = left
                break
    return overrides


def coerce_product_name_overrides(raw: str, app_ids: Sequence[str]) -> Dict[str, str]:
    """Map a plain display label onto selected product IDs (no id:name syntax)."""
    text = (raw or "").strip()
    overrides = parse_product_name_overrides(text)
    if overrides or not text or has_mapping_syntax(text):
        return overrides
    for pid in app_ids:
        key = str(pid).strip()
        if key:
            overrides[key] = text
    return overrides


def resolve_mvp_crawl_targets(
    platform: str,
    app_ids_raw: str,
    product_names_raw: str = "",
) -> tuple[List[str], Dict[str, str], List[str]]:
    """Resolve crawl IDs + display-name overrides for MVP refresh."""
    from src.services.analysis_wizard import resolve_game_inputs
    from src.services.google_play_pipeline import resolve_google_play_inputs
    from src.services.taptap_pipeline import resolve_taptap_inputs

    plat = (platform or "steam").strip().lower()
    id_text = (app_ids_raw or "").strip()
    name_text = (product_names_raw or "").strip()
    errors: List[str] = []

    overrides = parse_product_name_overrides(name_text)
    crawl_input = id_text
    if not crawl_input:
        if overrides:
            crawl_input = ",".join(overrides.keys())
        elif name_text and not has_mapping_syntax(name_text):
            crawl_input = name_text

    if not crawl_input:
        return [], {}, ["请至少选择一款产品，或在自定义产品名中填写游戏名/包名"]

    if plat == "taptap":
        resolved = resolve_taptap_inputs(crawl_input)
    elif plat == "google_play":
        resolved = resolve_google_play_inputs(crawl_input)
    else:
        resolved = resolve_game_inputs(crawl_input)

    app_ids = list(resolved.get("app_ids") or [])
    errors.extend(resolved.get("errors") or [])
    if not app_ids:
        msg = resolved.get("message") or "未能解析游戏 ID"
        errors.append(str(msg))
        return [], overrides, errors

    if not overrides and name_text:
        overrides = coerce_product_name_overrides(name_text, app_ids)

    return app_ids, overrides, errors


def apply_product_display_names(
    dataset: Dict[str, Any],
    overrides: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Rewrite product_name fields using registry + optional per-crawl overrides."""
    merged_overrides = dict(overrides or {})

    def _name_for(pid: str, current: str = "", platform: str = "") -> str:
        return lookup_display_name(
            pid,
            platform=platform,
            store_title=current,
            overrides=merged_overrides,
        )

    for game in dataset.get("games") or []:
        if not isinstance(game, dict):
            continue
        pid = str(game.get("app_id") or game.get("package_id") or "").strip()
        platform = str(game.get("platform") or "")
        if pid:
            game["name"] = _name_for(pid, str(game.get("name") or ""), platform)

    for bucket in ("comments", "metrics"):
        for row in dataset.get(bucket) or []:
            if not isinstance(row, dict):
                continue
            pid = str(row.get("product") or "").strip()
            platform = str(row.get("platform") or "")
            if pid:
                row["product_name"] = _name_for(pid, str(row.get("product_name") or ""), platform)

    custom_names = dataset.setdefault("custom_product_names", {})
    if isinstance(custom_names, dict):
        for pid, name in merged_overrides.items():
            custom_names[pid] = name

    return dataset

"""Derive filter options from the active comments/metrics dataset."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from src.mvp_data import get_mvp_analysis, normalize_time_period, record_product
from src.services.game_genre import infer_product_genre, lookup_steam_product_name

KNOWN_MOCK_PRODUCTS = {"game_a", "game_b", "game_c"}
_TEST_PRODUCT_NAME = re.compile(
    r"(?i)(ai测试|测试游戏|测试竞品|演示游戏|空拆解|demo\s*game|游戏[a-z]\s*[-—]|matrix\s*test|slime\s*farmer)"
)
KNOWN_MOCK_METRICS = {
    "用户总下载量",
    "平均用户在线时长",
    "付费付费占比 (ARPPU)",
    "7日留存率",
    "充值金额",
    "DAU/MAU",
}

_STEAM_APP_PLACEHOLDER = re.compile(r"^Steam App\s+\d+$", re.I)
_REF_GAME_ID = re.compile(r"^ref_", re.I)
_RANDOM_GAME_ID = re.compile(r"^game_[0-9a-f]{6,}$", re.I)
_SHOWCASE_PRODUCT_ORDER = ("730", "570", "10")


def is_meaningful_product(product_id: str, name: str) -> bool:
    """Drop library noise (numeric IDs, ref_* seeds, placeholder Steam names)."""
    pid = str(product_id or "").strip()
    label = str(name or "").strip()
    if not pid:
        return False
    if _REF_GAME_ID.match(pid):
        return False
    if pid in KNOWN_MOCK_PRODUCTS:
        return False
    if _TEST_PRODUCT_NAME.search(label):
        return False
    if lookup_steam_product_name(pid):
        return True
    if _RANDOM_GAME_ID.match(pid) and (
        not label or label == pid or _STEAM_APP_PLACEHOLDER.match(label)
    ):
        return False
    if label == pid or (label.isdigit() and pid.isdigit()):
        return False
    if _STEAM_APP_PLACEHOLDER.match(label):
        return False
    if len(label) >= 2 and label != pid:
        if any("\u4e00" <= c <= "\u9fff" for c in label):
            return True
        if any(c.isalpha() for c in label) and not label.replace(" ", "").isdigit():
            return True
    return False


def filter_meaningful_products(products: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    kept = [
        p
        for p in products
        if is_meaningful_product(str(p.get("id", "")), str(p.get("name", "")))
    ]

    def rank_key(p: Dict[str, Any]) -> tuple:
        pid = str(p.get("id", ""))
        if pid in _SHOWCASE_PRODUCT_ORDER:
            return (0, _SHOWCASE_PRODUCT_ORDER.index(pid), "")
        return (1, 0, str(p.get("name", "")).lower())

    kept.sort(key=rank_key)
    return kept


def _finalize_catalog_products(catalog: Dict[str, Any]) -> Dict[str, Any]:
    products = filter_meaningful_products(catalog.get("products") or [])
    genre_ids = sorted({p.get("genre") for p in products if p.get("genre")})
    genres = [{"id": g, "name": g} for g in genre_ids]
    return {**catalog, "products": products, "genres": genres or catalog.get("genres", [])}


def restrict_catalog_to_dataset(
    catalog: Dict[str, Any],
    comments: List[Dict[str, Any]],
    metrics: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Limit filter pickers to products/periods present in the active dataset."""
    data_ids: set[str] = set()
    for row in list(comments or []) + list(metrics or []):
        pid = record_product(row)
        if not pid:
            continue
        data_ids.add(pid)
        data_ids.add(_catalog_key(pid))
    if not data_ids:
        return catalog

    products = [
        p
        for p in (catalog.get("products") or [])
        if _catalog_key(str(p.get("id", ""))) in data_ids
        or str(p.get("id", "")) in data_ids
    ]
    periods = catalog.get("time_periods") or []
    period_ids: set[str] = set()
    for row in list(comments or []) + list(metrics or []):
        cycle = row.get("cycle") or row.get("周期")
        if cycle:
            period_ids.add(normalize_time_period(str(cycle)) or str(cycle))
    if period_ids:
        periods = [p for p in periods if p.get("id") in period_ids]
    return _finalize_catalog_products({**catalog, "products": products, "time_periods": periods})


GENRE_PRESETS = [
    "MOBA",
    "FPS",
    "Battle Royale",
    "RPG",
    "Open World",
    "Survival",
    "Simulation",
    "Horror",
    "Roguelike",
    "SLG",
    "Casual",
    "PC Game",
]


def metrics_dataset_usable(records: List[Dict[str, Any]]) -> bool:
    if not records:
        return False
    for row in records:
        if record_product(row) in KNOWN_MOCK_PRODUCTS:
            return True
        metric_name = str(row.get("metric") or "")
        if metric_name in KNOWN_MOCK_METRICS:
            return True
    return False


def _row_product_label(row: Dict[str, Any], product_id: str) -> Optional[str]:
    for key in ("product_name", "name", "产品"):
        raw = row.get(key)
        if raw in (None, ""):
            continue
        text = str(raw).strip()
        if text and text != str(product_id):
            return text
    return None


def _merge_product_name(names: Dict[str, str], product_id: str, label: Optional[str]) -> None:
    if not label:
        return
    prev = names.get(product_id)
    if not prev or prev == product_id:
        names[product_id] = label
        return
    if prev.isdigit() and not label.isdigit():
        names[product_id] = label


def _resolve_product_name(product_id: str, names: Dict[str, str]) -> str:
    explicit = names.get(product_id)
    if explicit and explicit != str(product_id):
        return explicit
    known = lookup_steam_product_name(product_id)
    if known:
        return known
    return explicit or str(product_id)


def derive_data_catalog(
    comments: List[Dict[str, Any]],
    metrics: List[Dict[str, Any]],
) -> Dict[str, Any]:
    names: Dict[str, str] = {}
    genres: Dict[str, str] = {}
    platforms: Dict[str, str] = {}
    periods: Dict[str, str] = {}
    seen_products: set[str] = set()

    for row in list(comments or []) + list(metrics or []):
        product_id = record_product(row)
        if product_id:
            seen_products.add(product_id)
            _merge_product_name(names, product_id, _row_product_label(row, product_id))
            plat = row.get("platform") or row.get("channel") or row.get("平台")
            if plat and product_id not in platforms:
                platforms[product_id] = str(plat).strip()

        cycle = row.get("cycle") or row.get("周期")
        if cycle:
            cycle_str = str(cycle)
            period_id = normalize_time_period(cycle_str) or cycle_str
            periods[period_id] = cycle_str

    for product_id in seen_products:
        resolved = _resolve_product_name(product_id, names)
        names[product_id] = resolved
        genres[product_id] = infer_product_genre(product_id, resolved)

    genre_set = sorted({g for g in genres.values() if g})

    catalog = {
        "products": [
            {
                "id": pid,
                "name": names[pid],
                "genre": genres.get(pid, "PC Game"),
                "platform": platforms.get(pid, ""),
            }
            for pid in sorted(names.keys())
        ],
        "genres": [{"id": g, "name": g} for g in genre_set],
        "time_periods": [{"id": pid, "name": name} for pid, name in sorted(periods.items())],
    }
    return _finalize_catalog_products(catalog)


def _catalog_product_keys(game: Dict[str, Any]) -> List[str]:
    keys: List[str] = []
    steam_id = str(game.get("steam_app_id") or "").strip()
    game_id = str(game.get("game_id") or "").strip()
    if steam_id:
        keys.append(steam_id)
    if game_id.startswith("steam_"):
        bare = game_id.replace("steam_", "", 1)
        if bare not in keys:
            keys.append(bare)
    if game_id and game_id not in keys:
        keys.append(game_id)
    return keys


def _catalog_key(product_id: str) -> str:
    pid = str(product_id or "").strip()
    if pid.startswith("steam_") and pid[6:].isdigit():
        return pid[6:]
    return pid


def _prefer_product_name(product_id: str, current: str, candidate: str) -> str:
    cur = str(current or "").strip()
    cand = str(candidate or "").strip()
    if not cand:
        return cur or str(product_id)
    if not cur or cur == str(product_id):
        return cand
    if cand == str(product_id) or cand.startswith("Steam App "):
        return cur
    if cur.startswith("Steam App ") and not cand.startswith("Steam App "):
        return cand
    return cur


def enrich_catalog_from_context(
    catalog: Dict[str, Any],
    *,
    username: Optional[str] = None,
) -> Dict[str, Any]:
    """Merge game library + MVP analysis names/genres into filter catalog."""
    products: Dict[str, Dict[str, Any]] = {}
    for item in catalog.get("products") or []:
        key = _catalog_key(str(item["id"]))
        products[key] = {**item, "id": key}

    genre_names = {g.get("id") or g.get("name") for g in catalog.get("genres") or [] if g}

    analysis = get_mvp_analysis() or {}
    product_reports = analysis.get("product_reports") or {}
    if isinstance(product_reports, dict):
        for pid, report in product_reports.items():
            if not isinstance(report, dict):
                continue
            key = _catalog_key(str(pid))
            label = str(report.get("product_name") or report.get("name") or "").strip()
            if not label:
                continue
            entry = products.get(key, {"id": key, "name": key, "genre": "PC Game"})
            entry["name"] = _prefer_product_name(key, entry.get("name", key), label)
            entry["genre"] = infer_product_genre(key, entry["name"])
            products[key] = entry
            genre_names.add(entry["genre"])

    try:
        from src.services.game_intel import GameLibraryRepository

        for game in GameLibraryRepository.list_games(username=username, limit=200):
            game_id = str(game.get("game_id") or "").strip()
            if _REF_GAME_ID.match(game_id):
                continue
            name = str(game.get("name") or "").strip()
            if not name or _TEST_PRODUCT_NAME.search(name):
                continue
            if str(game.get("game_id") or "") in KNOWN_MOCK_PRODUCTS:
                continue
            genre = str(game.get("genre") or game.get("sub_genre") or "").strip()
            for raw_key in _catalog_product_keys(game):
                key = _catalog_key(raw_key)
                entry = products.get(key, {"id": key, "name": key, "genre": genre or "PC Game"})
                entry["name"] = _prefer_product_name(key, entry.get("name", key), name)
                if genre:
                    entry["genre"] = genre
                elif not entry.get("genre"):
                    entry["genre"] = infer_product_genre(key, entry["name"])
                products[key] = entry
                genre_names.add(entry["genre"])
            if genre:
                genre_names.add(genre)
    except Exception:
        pass

    for key, entry in list(products.items()):
        resolved = _prefer_product_name(
            key,
            entry.get("name", key),
            lookup_steam_product_name(key),
        )
        entry["name"] = resolved
        inferred = infer_product_genre(key, resolved)
        lib_genre = entry.get("genre")
        entry["genre"] = lib_genre if lib_genre and lib_genre != "PC Game" else inferred
        products[key] = entry
        genre_names.add(entry["genre"])

    for preset in GENRE_PRESETS:
        genre_names.add(preset)

    merged = {
        **catalog,
        "products": [
            products[pid]
            for pid in sorted(products.keys(), key=lambda x: (products[x].get("name") or x).lower())
        ],
        "genres": [{"id": g, "name": g} for g in sorted(g for g in genre_names if g)],
    }
    return _finalize_catalog_products(merged)

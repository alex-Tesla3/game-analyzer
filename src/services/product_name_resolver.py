"""Resolve catalog product IDs to display names for reports and analytics."""

from __future__ import annotations

from typing import Dict, List, Optional

from src.data_catalog import derive_data_catalog, enrich_catalog_from_context
from src.data_resolution import get_user_comments_data, get_user_metrics_data
from src.product_registry import get_mvp_presets, lookup_display_name
from src.services.legacy_ai_report import MOCK_PRODUCT_NAMES


def build_product_name_map(
    product_ids: Optional[List[str]] = None,
    *,
    username: Optional[str] = None,
) -> Dict[str, str]:
    """Merge mock, crawled catalog, registry presets, and lookup fallbacks."""
    names: Dict[str, str] = dict(MOCK_PRODUCT_NAMES)

    if username:
        comments = get_user_comments_data(username) or []
        metrics = get_user_metrics_data(username) or []
        catalog = enrich_catalog_from_context(
            derive_data_catalog(comments, metrics),
            username=username,
        )
        for item in catalog.get("products") or []:
            pid = str(item.get("id") or "").strip()
            if pid:
                names[pid] = str(item.get("name") or pid).strip() or pid

    for preset in get_mvp_presets():
        pid = str(preset.get("id") or "").strip()
        if pid:
            names.setdefault(pid, str(preset.get("name") or pid).strip() or pid)

    for pid in product_ids or []:
        token = str(pid or "").strip()
        if not token or token == "all":
            continue
        if token not in names or names[token] == token:
            resolved = lookup_display_name(token)
            if resolved:
                names[token] = resolved

    return names


def label_for_products(product_ids: List[str], name_map: Dict[str, str]) -> str:
    if not product_ids or product_ids == ["all"]:
        return "全部产品"
    labels = [name_map.get(pid, pid) for pid in product_ids if pid and pid != "all"]
    return "、".join(labels) if labels else "全部产品"

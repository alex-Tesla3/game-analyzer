"""Merge platform crawl batches into the shared MVP dataset artifact."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Sequence, Set

from src.mvp_pipeline import DEFAULT_OUTPUT_DIR, analyze_actual_steam_data, validate_analysis


def _normalize_platform(value: Any) -> str:
    return str(value or "").strip().lower().replace("_", " ")


def _product_ids_from_dataset(dataset: Dict[str, Any]) -> Set[str]:
    ids: Set[str] = set()
    for game in dataset.get("games") or []:
        for key in ("package_id", "app_id", "product"):
            raw = game.get(key)
            if raw:
                ids.add(str(raw).strip())
    for row in dataset.get("comments") or []:
        raw = row.get("product")
        if raw:
            ids.add(str(raw).strip())
    for row in dataset.get("metrics") or []:
        raw = row.get("product")
        if raw:
            ids.add(str(raw).strip())
    return {item for item in ids if item}


def _strip_platform_products(
    existing: Dict[str, Any],
    *,
    platform: str,
    product_ids: Iterable[str],
) -> Dict[str, Any]:
    """Drop prior rows for products being re-crawled on the same platform."""
    target_platform = _normalize_platform(platform)
    replace_ids = {str(pid).strip() for pid in product_ids if str(pid).strip()}
    if not replace_ids:
        return existing

    def row_product(row: Dict[str, Any]) -> str:
        return str(row.get("product") or "").strip()

    def row_platform(row: Dict[str, Any]) -> str:
        return _normalize_platform(row.get("platform") or row.get("channel") or row.get("平台"))

    def game_product_id(game: Dict[str, Any]) -> str:
        return str(game.get("package_id") or game.get("app_id") or game.get("product") or "").strip()

    def game_platform(game: Dict[str, Any]) -> str:
        return _normalize_platform(game.get("platform"))

    comments = [
        row
        for row in (existing.get("comments") or [])
        if not (row_product(row) in replace_ids and row_platform(row) == target_platform)
    ]
    metrics = [
        row
        for row in (existing.get("metrics") or [])
        if not (row_product(row) in replace_ids and row_platform(row) == target_platform)
    ]
    games = [
        game
        for game in (existing.get("games") or [])
        if not (game_product_id(game) in replace_ids and game_platform(game) == target_platform)
    ]
    return {**existing, "comments": comments, "metrics": metrics, "games": games}


def merge_platform_dataset(
    platform_dataset: Dict[str, Any],
    *,
    platform: str,
    output_dir: str = DEFAULT_OUTPUT_DIR,
    platform_artifact_name: str,
    extra_platforms: Sequence[str] = (),
) -> Dict[str, Any]:
    out_dir = os.path.abspath(output_dir)
    os.makedirs(out_dir, exist_ok=True)
    steam_path = os.path.join(out_dir, "steam_dataset.json")
    existing: Dict[str, Any] = {"comments": [], "metrics": [], "games": []}
    if os.path.exists(steam_path):
        with open(steam_path, "r", encoding="utf-8") as handle:
            existing = json.load(handle)

    replace_ids = _product_ids_from_dataset(platform_dataset)
    existing = _strip_platform_products(existing, platform=platform, product_ids=replace_ids)

    platforms = set(existing.get("platforms") or [])
    platforms.update(extra_platforms)
    platforms.add(platform)

    merged = {
        "source": "mvp_multi",
        "crawled_at": datetime.now(timezone.utc).isoformat(),
        "review_days": platform_dataset.get("review_days"),
        "games": list(existing.get("games") or []) + list(platform_dataset.get("games") or []),
        "comments": list(existing.get("comments") or []) + list(platform_dataset.get("comments") or []),
        "metrics": list(existing.get("metrics") or []) + list(platform_dataset.get("metrics") or []),
        "platforms": sorted(platforms),
        "data_mode": platform_dataset.get("data_mode", "live"),
    }
    analysis = analyze_actual_steam_data(merged["comments"], merged["metrics"])
    validation = validate_analysis(merged["comments"], merged["metrics"], analysis)

    batch_comments = list(platform_dataset.get("comments") or [])
    batch_metrics = list(platform_dataset.get("metrics") or [])
    batch_analysis = analyze_actual_steam_data(batch_comments, batch_metrics)
    batch_validation = validate_analysis(batch_comments, batch_metrics, batch_analysis)
    platform_payload = {
        **platform_dataset,
        "analysis": batch_analysis,
        "validation": batch_validation,
    }

    with open(steam_path, "w", encoding="utf-8") as handle:
        json.dump(merged, handle, ensure_ascii=False, indent=2)
    with open(os.path.join(out_dir, platform_artifact_name), "w", encoding="utf-8") as handle:
        json.dump(platform_payload, handle, ensure_ascii=False, indent=2)
    with open(os.path.join(out_dir, "analysis.json"), "w", encoding="utf-8") as handle:
        json.dump(analysis, handle, ensure_ascii=False, indent=2)
    with open(os.path.join(out_dir, "validation.json"), "w", encoding="utf-8") as handle:
        json.dump(validation, handle, ensure_ascii=False, indent=2)

    return {
        "success": bool(validation.get("passed")),
        "validation": validation,
        "artifacts": {
            "dataset": steam_path,
            "analysis": os.path.join(out_dir, "analysis.json"),
            "validation": os.path.join(out_dir, "validation.json"),
        },
    }

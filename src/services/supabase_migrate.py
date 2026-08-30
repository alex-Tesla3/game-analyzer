"""把本地爬取数据集(JSON)迁移到 Supabase —— 可被脚本或应用内 API 调用。"""

from __future__ import annotations

import glob
import json
import os
from typing import Any, Dict, List, Optional, Tuple

from src.services import supabase_store
from src.services.data_agent import normalize_review


def collect_datasets(root: Optional[str] = None) -> List[Tuple[str, Dict[str, Any]]]:
    root = root or os.path.join(os.path.dirname(__file__), "..", "..", "data", "mvp")
    files = sorted(glob.glob(os.path.join(root, "**", "*.json"), recursive=True))
    out = []
    for path in files:
        if "snapshots" in path or "validation" in path or "analysis" in path:
            continue
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            if isinstance(data, dict) and ("comments" in data or "games" in data):
                out.append((path, data))
        except (OSError, ValueError):
            continue
    return out


def run_migration(*, embed: bool = False) -> Dict[str, Any]:
    """执行 schema + 数据迁移, 返回统计。"""
    if not supabase_store.enabled():
        return {"success": False, "error": "SUPABASE_DATABASE_URL 未配置"}

    result: Dict[str, Any] = {"success": True, "datasets": 0}
    try:
        result["schema"] = supabase_store.ensure_schema()
    except Exception as exc:
        return {"success": False, "error": f"schema 初始化失败: {exc}"}

    datasets = collect_datasets()
    result["datasets"] = len(datasets)
    totals = {"games": 0, "reviews": 0, "metrics": 0, "labels": 0, "embeddings": 0}
    result["files"] = []

    for path, data in datasets:
        games = data.get("games") or []
        raw_comments = data.get("comments") or []
        metrics = data.get("metrics") or []
        reviews = [normalize_review(r, i) for i, r in enumerate(raw_comments)]

        game_rows = [
            {
                "game_id": g.get("app_id") or g.get("game_id") or str(g.get("id", "")),
                "platform": str(g.get("platform", "steam")).lower(),
                "name": g.get("name") or g.get("product_name") or "unknown",
                "genre": g.get("genre"),
                "metadata": g,
            }
            for g in games
        ]
        metric_rows = [
            {
                "game_id": m.get("product") or m.get("app_id") or m.get("game_id") or "",
                "platform": str(m.get("platform", "steam")).lower(),
                "metric_date": str(m.get("date") or m.get("日期") or ""),
                "metric_type": str(m.get("metric") or m.get("指标") or "unknown"),
                "value": _to_float(m.get("值") or m.get("value")),
                "raw": m,
            }
            for m in metrics
        ]
        label_rows = [
            {
                "review_id": r["review_id"],
                "sentiment": str(r.get("情绪") or "neutral"),
                "topics": [], "aspects": {},
                "intent": "other", "spam_probability": 0.0,
                "label_source": "rule",
            }
            for r in raw_comments
        ]

        totals["games"] += supabase_store.upsert_games(game_rows)
        totals["reviews"] += supabase_store.upsert_reviews(reviews)
        totals["metrics"] += supabase_store.upsert_metrics(metric_rows)
        totals["labels"] += supabase_store.upsert_labels(label_rows)

        if embed:
            totals["embeddings"] += _embed_dataset(reviews)

        result["files"].append({
            "path": os.path.relpath(path, os.getcwd()),
            "games": len(game_rows),
            "reviews": len(reviews),
            "metrics": len(metric_rows),
        })

    result["totals"] = totals
    return result


def _embed_dataset(reviews: List[Dict[str, Any]]) -> int:
    import asyncio

    from src.services.llm_client import embed_texts

    to_embed = [r for r in reviews if r.get("content", "").strip()]
    rows = []
    for i in range(0, len(to_embed), 64):
        batch = to_embed[i : i + 64]
        vectors = asyncio.run(embed_texts([r["content"] for r in batch]))
        for r, vec in zip(batch, vectors):
            rows.append({"review_id": r["review_id"], "embedding": list(vec), "model": "default"})
    return supabase_store.upsert_embeddings(rows)


def _to_float(value) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

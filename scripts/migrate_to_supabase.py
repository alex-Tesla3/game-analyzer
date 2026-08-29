#!/usr/bin/env python3
"""把现有爬取数据集(JSON)迁移到 Supabase。

用法:
    .venv/bin/python scripts/migrate_to_supabase.py [--embed]
    --embed  同时为评论生成 embedding(需配置 OpenAI/Ollama)

要求: SUPABASE_DATABASE_URL 环境变量(或 .env 中配置)。
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from src.env_loader import load_env_file  # noqa: E402

load_env_file(str(ROOT / ".env"))

from src.services import supabase_store  # noqa: E402
from src.services.data_agent import normalize_review  # noqa: E402


def collect_datasets() -> list:
    files = sorted(
        glob.glob(str(ROOT / "data" / "mvp" / "**" / "*.json"), recursive=True)
    )
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate dataset JSON to Supabase")
    parser.add_argument("--embed", action="store_true", help="同时生成评论 embedding")
    args = parser.parse_args()

    if not supabase_store.enabled():
        print("错误: 未配置 SUPABASE_DATABASE_URL(可写入 .env)")
        return 1

    print("初始化 schema ...")
    try:
        info = supabase_store.ensure_schema()
        print(f"  schema OK (dim={info['dim']}, host={info['url_host']})")
    except Exception as exc:
        print(f"  schema 失败: {exc}")
        return 1

    datasets = collect_datasets()
    print(f"发现 {len(datasets)} 个数据集")

    total_games = total_reviews = total_metrics = total_labels = total_noise = total_emb = 0
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
        review_rows = [dict(r) for r in reviews]
        label_rows = [
            {"review_id": r["review_id"], "label_source": "rule",
             "sentiment": (r.get("情绪") or "neutral"), "topics": [], "aspects": {},
             "intent": "other", "spam_probability": 0.0}
            for r in raw_comments
        ]

        total_games += supabase_store.upsert_games(game_rows)
        total_reviews += supabase_store.upsert_reviews(review_rows)
        total_metrics += supabase_store.upsert_metrics(metric_rows)
        total_labels += supabase_store.upsert_labels(label_rows)

        if args.embed:
            try:
                import asyncio
                from src.services.llm_client import embed_texts

                to_embed = [r for r in reviews if r.get("content", "").strip()]
                emb_rows = []
                for i in range(0, len(to_embed), 64):
                    batch = to_embed[i : i + 64]
                    vectors = asyncio.run(embed_texts([r["content"] for r in batch]))
                    for r, vec in zip(batch, vectors):
                        emb_rows.append({"review_id": r["review_id"], "embedding": list(vec), "model": "default"})
                total_emb += supabase_store.upsert_embeddings(emb_rows)
            except Exception as exc:
                print(f"  [警告] {path} embedding 失败: {exc}")
        print(f"  {os.path.relpath(path, ROOT)}: {len(game_rows)} games, "
              f"{len(review_rows)} reviews, {len(metric_rows)} metrics"
              + (f", {total_emb} embeddings" if args.embed else ""))

    print("\n迁移完成:")
    print(f"  games: {total_games}, reviews: {total_reviews}, metrics: {total_metrics}")
    print(f"  labels: {total_labels}, embeddings: {total_emb}")
    return 0


def _to_float(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


if __name__ == "__main__":
    raise SystemExit(main())

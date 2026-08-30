#!/usr/bin/env python3
"""把现有爬取数据集(JSON)迁移到 Supabase(CLI 入口)。

用法:
    .venv/bin/python scripts/migrate_to_supabase.py [--embed]

也可通过应用内接口触发(无需 Shell):
    POST /api/agent/migrate  (管理员 token 或 X-Migrate-Secret)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from src.env_loader import load_env_file  # noqa: E402

load_env_file(str(ROOT / ".env"))

from src.services.supabase_migrate import run_migration  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate dataset JSON to Supabase")
    parser.add_argument("--embed", action="store_true", help="同时生成评论 embedding(需配置 OpenAI/Ollama)")
    args = parser.parse_args()

    result = run_migration(embed=args.embed)
    if not result.get("success"):
        print("错误:", result.get("error"))
        return 1

    print(f"schema: {result['schema']}")
    print(f"数据集: {result['datasets']} 个")
    for item in result.get("files", []):
        print(f"  {item['path']}: {item['games']} games, {item['reviews']} reviews, {item['metrics']} metrics")
    totals = result.get("totals", {})
    print("\n迁移完成:")
    print(f"  games: {totals.get('games', 0)}, reviews: {totals.get('reviews', 0)}, "
          f"metrics: {totals.get('metrics', 0)}, labels: {totals.get('labels', 0)}, "
          f"embeddings: {totals.get('embeddings', 0)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

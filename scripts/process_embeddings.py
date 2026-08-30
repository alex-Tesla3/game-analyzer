#!/usr/bin/env python3
"""本地 Ollama 补全向量 + 主题簇, 并写入 Supabase。

在您本机开着 Ollama 时执行, 把最新评论的 embedding 和聚类主题补进 Supabase
(Render 自动处理时因无 Ollama 会跳过 embed/cluster, 由本脚本补齐)。

用法:
    .venv/bin/python scripts/process_embeddings.py [username] [--dataset PATH] [--retries N]
默认 username=demo; --retries 控制 Supabase 连接重试(网络不稳时调大)。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from src.env_loader import load_env_file  # noqa: E402

load_env_file(str(ROOT / ".env"))


def main() -> int:
    parser = argparse.ArgumentParser(description="本地 Ollama 补向量/主题并入库 Supabase")
    parser.add_argument("username", nargs="?", default="demo", help="数据集归属用户名(默认 demo)")
    parser.add_argument("--dataset", default="", help="指定数据集 JSON 路径")
    parser.add_argument("--retries", type=int, default=0, help="Supabase 连接重试次数(0=用 .env 配置)")
    args = parser.parse_args()

    if args.retries > 0:
        os.environ["SUPABASE_CONNECT_RETRIES"] = str(args.retries)

    # 本地 LLM -> Ollama(持久化到 DB, 管道内 refresh 会读取)
    from database import LLMConfigRepository

    LLMConfigRepository.save({
        "provider": "ollama",
        "model": "qwen3.5:latest",
        "api_key": "",
        "endpoint": "http://127.0.0.1:11434",
    })
    os.environ["EMBEDDING_MODEL"] = "all-minilm"
    os.environ["EMBEDDING_DIM"] = "384"

    import asyncio

    from src.services.data_agent import run_data_agent

    report = asyncio.run(
        run_data_agent(
            args.username,
            dataset_path=args.dataset,
            steps=["embed", "cluster", "store", "aggregate"],
            use_llm=False,
        )
    )
    print(json.dumps(report, ensure_ascii=False, indent=2)[:4000])
    store = (report.get("steps") or {}).get("store") or {}
    if store.get("error"):
        print("\n⚠️ store 未成功(网络窗口问题), 重试: 提高 --retries 或稍后再跑")
        return 1
    print("\n✅ 向量/主题已补全入库")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

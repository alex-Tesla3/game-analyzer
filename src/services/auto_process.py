"""爬取完成事件 -> 自动触发 Agent 管道(后台, 不阻塞请求)。

开启方式: 环境变量 AUTO_PROCESS_AFTER_CRAWL=true
"""

from __future__ import annotations

import os
import threading
from typing import Optional


def auto_process_enabled() -> bool:
    return os.getenv("AUTO_PROCESS_AFTER_CRAWL", "false").strip().lower() in {
        "1", "true", "yes", "on",
    }


def maybe_trigger_auto_process(username: str, output_dir: str) -> Optional[dict]:
    """数据集已生成后调用; 返回 None 表示未开启/无数据集。"""
    if not auto_process_enabled():
        return None
    dataset_path = os.path.join(output_dir, "steam_dataset.json")
    if not os.path.isfile(dataset_path):
        return None
    thread = threading.Thread(
        target=_run_agent_in_thread,
        args=(username, dataset_path),
        daemon=True,
        name="auto-agent-process",
    )
    thread.start()
    return {"triggered": True, "dataset": dataset_path}


def _run_agent_in_thread(username: str, dataset_path: str) -> None:
    import asyncio

    from src.services.data_agent import run_data_agent

    try:
        report = asyncio.run(
            run_data_agent(
                username,
                dataset_path=dataset_path,
                steps=["clean", "label", "embed", "cluster", "store", "aggregate"],
                use_llm=True,
            )
        )
        print(f"[auto-process] {username}: done, success={report.get('success')}")
        if report.get("steps", {}).get("store", {}).get("error"):
            print(f"[auto-process] store 跳过: {report['steps']['store']['error'][:120]}")
    except Exception as exc:  # noqa: BLE001
        print(f"[auto-process] {username} failed: {exc}")

"""Rate-limited, parallel product crawling helpers."""

from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Dict, Iterable, Optional, TypeVar

R = TypeVar("R")


def crawl_delay_seconds() -> float:
    raw = os.getenv("GA_CRAWL_DELAY_SECONDS", "0.4")
    try:
        return max(0.0, float(raw))
    except ValueError:
        return 0.4


def crawl_product_delay_seconds() -> float:
    """Pause between finishing one product and starting the next."""
    raw = os.getenv("GA_CRAWL_PRODUCT_DELAY_SECONDS", "2.0")
    try:
        return max(0.0, float(raw))
    except ValueError:
        return 2.0


def throttle_between_products() -> None:
    delay = crawl_product_delay_seconds()
    if delay > 0:
        time.sleep(delay)


def crawl_max_workers() -> int:
    raw = os.getenv("GA_CRAWL_MAX_WORKERS", "3")
    try:
        return max(1, min(int(raw), 8))
    except ValueError:
        return 3


def throttle_page_fetch() -> None:
    delay = crawl_delay_seconds()
    if delay > 0:
        time.sleep(delay)


def crawl_products_parallel(
    product_ids: Iterable[str],
    crawl_one: Callable[[str], R],
    *,
    max_workers: Optional[int] = None,
) -> Dict[str, R]:
    """Crawl multiple products concurrently; each worker should use its own HTTP session."""
    ids = [str(item).strip() for item in product_ids if str(item).strip()]
    if not ids:
        return {}
    workers = max_workers if max_workers is not None else crawl_max_workers()
    if len(ids) == 1 or workers <= 1:
        return {pid: crawl_one(pid) for pid in ids}

    results: Dict[str, R] = {}
    with ThreadPoolExecutor(max_workers=min(workers, len(ids))) as pool:
        futures = {pool.submit(crawl_one, pid): pid for pid in ids}
        for future in as_completed(futures):
            pid = futures[future]
            results[pid] = future.result()
    return results

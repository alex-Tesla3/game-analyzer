import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.services.mvp_dataset_merge import _strip_platform_products


def test_strip_platform_products_replaces_only_matching_gp_rows():
    existing = {
        "comments": [
            {"product": "com.a", "platform": "Google Play", "内容": "old-a"},
            {"product": "com.b", "platform": "Google Play", "内容": "keep-b"},
            {"product": "730", "platform": "Steam", "内容": "steam"},
        ],
        "metrics": [
            {"product": "com.a", "platform": "Google Play", "metric": "抓取评论数", "值": 1},
            {"product": "com.b", "platform": "Google Play", "metric": "抓取评论数", "值": 2},
        ],
        "games": [
            {"package_id": "com.a", "platform": "Google Play", "name": "A"},
            {"package_id": "com.b", "platform": "Google Play", "name": "B"},
        ],
    }
    stripped = _strip_platform_products(existing, platform="Google Play", product_ids=["com.a"])
    assert [c["内容"] for c in stripped["comments"]] == ["keep-b", "steam"]
    assert [m["product"] for m in stripped["metrics"]] == ["com.b"]
    assert [g["package_id"] for g in stripped["games"]] == ["com.b"]

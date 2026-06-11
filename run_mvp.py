#!/usr/bin/env python3
"""Run the game analyzer MVP with real Steam public data."""

from __future__ import annotations

import argparse
import json
import os
import sys

from src.mvp_pipeline import DEFAULT_STEAM_APP_IDS, run_mvp_pipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Crawl real Steam data and validate analysis.")
    parser.add_argument(
        "--app-ids",
        default=",".join(DEFAULT_STEAM_APP_IDS),
        help="Comma-separated Steam app ids. Defaults to CS2, Dota 2, and Apex Legends.",
    )
    parser.add_argument(
        "--review-days",
        type=int,
        default=14,
        help="Only keep reviews from the last N days (allowed: 7, 14, 30).",
    )
    parser.add_argument(
        "--output-dir",
        default=os.path.join("data", "mvp"),
        help="Directory for dataset, analysis, and validation JSON artifacts.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    app_ids = [item.strip() for item in args.app_ids.split(",") if item.strip()]
    result = run_mvp_pipeline(
        app_ids=app_ids,
        output_dir=args.output_dir,
        review_days=args.review_days,
    )
    summary = {
        "success": result["success"],
        "products": result["analysis"]["summary"]["total_products"],
        "comments": result["analysis"]["summary"]["total_comments"],
        "overall_positive_rate": result["analysis"]["summary"]["overall_positive_rate"],
        "validation_passed": result["validation"]["passed"],
        "artifacts": result["artifacts"],
        "crawl_errors": result["dataset"].get("errors", []),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if result["success"] else 1


if __name__ == "__main__":
    sys.exit(main())

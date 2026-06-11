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
        "--use-review-days",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Filter reviews by publish date window.",
    )
    parser.add_argument(
        "--review-days",
        type=int,
        default=30,
        help="Only keep reviews from the last N days when --use-review-days (allowed: 7, 14, 30).",
    )
    parser.add_argument(
        "--use-max-reviews",
        action="store_true",
        help="Cap reviews per product at --max-reviews.",
    )
    parser.add_argument(
        "--max-reviews",
        type=int,
        default=0,
        help="Max reviews per product when --use-max-reviews (no system cap).",
    )
    parser.add_argument(
        "--market-country",
        default="us",
        help="Steam store country/region for review language (e.g. us, cn, jp).",
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
        use_review_days=args.use_review_days,
        use_max_reviews=args.use_max_reviews,
        max_reviews_per_app=args.max_reviews or None,
        market_country=args.market_country,
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

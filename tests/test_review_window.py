import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.services.review_window import (
    collect_recent_reviews_within_days,
    filter_raw_reviews_by_days,
    normalize_review_days,
    review_is_within_days,
    steam_review_datetime,
)


def test_normalize_review_days_accepts_allowed_values():
    assert normalize_review_days(0) == 30
    assert normalize_review_days(7) == 7
    assert normalize_review_days(14) == 14
    assert normalize_review_days(30) == 30
    assert normalize_review_days(15) == 30
    assert normalize_review_days("14") == 14


def test_filter_raw_reviews_by_days_keeps_recent_only():
    now = datetime.now(timezone.utc)
    reviews = [
        {"timestamp_created": int((now - timedelta(days=2)).timestamp())},
        {"timestamp_created": int((now - timedelta(days=20)).timestamp())},
        {"timestamp_created": int((now - timedelta(days=5)).timestamp())},
    ]
    kept = filter_raw_reviews_by_days(
        reviews, 7, date_fn=steam_review_datetime, max_count=10
    )
    assert len(kept) == 2


def test_collect_recent_reviews_stops_when_batch_is_older_than_window():
    now = datetime.now(timezone.utc)

    def batches():
        yield [
            {"timestamp_created": int((now - timedelta(days=1)).timestamp())},
            {"timestamp_created": int((now - timedelta(days=3)).timestamp())},
        ]
        yield [
            {"timestamp_created": int((now - timedelta(days=40)).timestamp())},
        ]

    collected = collect_recent_reviews_within_days(
        batches(),
        days=7,
        max_count=10,
        date_fn=steam_review_datetime,
    )
    assert len(collected) == 2


def test_review_is_within_days_rejects_missing_timestamp():
    assert review_is_within_days(None, 7) is False

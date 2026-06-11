"""Filter crawled reviews by rolling calendar window (e.g. last 7 / 14 days)."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence

DEFAULT_REVIEW_DAYS = 30
ALLOWED_REVIEW_DAYS = (7, 14, 30)


def normalize_review_days(value: Any) -> int:
    """Return one of 7, 14, 30 (default 14)."""
    try:
        days = int(value or 0)
    except (TypeError, ValueError):
        return DEFAULT_REVIEW_DAYS
    return days if days in ALLOWED_REVIEW_DAYS else DEFAULT_REVIEW_DAYS


def review_days_label(days: int) -> str:
    normalized = normalize_review_days(days)
    if normalized == 7:
        return "近 7 天"
    if normalized == 14:
        return "近 14 天"
    return "近 30 天"


def cutoff_datetime(days: int, *, now: Optional[datetime] = None) -> datetime:
    normalized = normalize_review_days(days)
    anchor = now or datetime.now(timezone.utc)
    if anchor.tzinfo is None:
        anchor = anchor.replace(tzinfo=timezone.utc)
    return anchor - timedelta(days=normalized)


def _to_utc_datetime(value: Any) -> Optional[datetime]:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, date):
        dt = datetime(value.year, value.month, value.day, tzinfo=timezone.utc)
    elif isinstance(value, (int, float)):
        ts = float(value)
        if ts > 1_000_000_000_000:
            ts /= 1000.0
        dt = datetime.fromtimestamp(ts, timezone.utc)
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if text.isdigit():
            return _to_utc_datetime(int(text))
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(text)
        except ValueError:
            return None
    else:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def review_datetime_from_comment(comment: Dict[str, Any]) -> Optional[datetime]:
    for key in ("日期", "date", "review_date", "created_at"):
        dt = _to_utc_datetime(comment.get(key))
        if dt:
            return dt
    return None


def steam_review_datetime(review: Dict[str, Any]) -> Optional[datetime]:
    for key in ("timestamp_created", "timestamp_updated"):
        dt = _to_utc_datetime(review.get(key))
        if dt:
            return dt
    return None


def taptap_review_datetime(review: Dict[str, Any]) -> Optional[datetime]:
    for key in ("created_time", "updated_time", "publish_time", "timestamp"):
        dt = _to_utc_datetime(review.get(key))
        if dt:
            return dt
    return None


def gplay_review_datetime(review: Dict[str, Any]) -> Optional[datetime]:
    for key in ("at", "review_date", "timestamp"):
        dt = _to_utc_datetime(review.get(key))
        if dt:
            return dt
    return None


def review_is_within_days(dt: Optional[datetime], days: int, *, now: Optional[datetime] = None) -> bool:
    if dt is None:
        return False
    return dt >= cutoff_datetime(days, now=now)


def iso_date_from_datetime(dt: Optional[datetime]) -> str:
    if not dt:
        return ""
    return dt.astimezone(timezone.utc).date().isoformat()


def filter_raw_reviews_by_days(
    reviews: Sequence[Dict[str, Any]],
    days: int,
    *,
    date_fn,
    max_count: Optional[int] = None,
) -> List[Dict[str, Any]]:
    kept: List[Dict[str, Any]] = []
    for review in reviews:
        if review_is_within_days(date_fn(review), days):
            kept.append(review)
            if max_count is not None and len(kept) >= max_count:
                break
    return kept


def collect_recent_reviews_within_days(
    batches: Iterable[Sequence[Dict[str, Any]]],
    *,
    days: int,
    date_fn,
    max_count: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Paginate newest-first batches until the time window is exhausted (no default cap)."""
    collected: List[Dict[str, Any]] = []
    for batch in batches:
        if not batch:
            break
        saw_in_window = False
        saw_outside_window = False
        for review in batch:
            dt = date_fn(review)
            if review_is_within_days(dt, days):
                collected.append(review)
                saw_in_window = True
                if max_count is not None and len(collected) >= max_count:
                    return collected
            elif dt is not None:
                saw_outside_window = True
        if saw_outside_window and not saw_in_window:
            break
    return collected

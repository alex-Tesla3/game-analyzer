"""Resolve comments/metrics for API handlers (imported > MVP > cached > mock)."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional, Tuple

from src.database import ImportedDataRepository
from src.data_catalog import metrics_dataset_usable
from src.mvp_data import get_mvp_comments_and_metrics, mvp_validation_passed, record_product
from src.services.mvp_storage import resolve_mvp_output_dir

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "..", "mock_data")

TEST_ONLY_PRODUCTS = frozenset({"test", "demo", "unknown"})


def load_data(file_path: str) -> Any:
    try:
        with open(file_path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
            if isinstance(data, list):
                return data
            raise ValueError("Data loaded is not a list.")
    except FileNotFoundError:
        print(f"错误：找不到文件 {file_path}")
        return None
    except json.JSONDecodeError as exc:
        print(f"错误：JSON解析失败，请检查 {file_path} 文件。错误信息: {exc}")
        return None


def get_comments_data() -> List[Dict]:
    data = load_data(os.path.join(DATA_DIR, "comments.json"))
    return data or []


def get_metrics_data() -> List[Dict]:
    data = load_data(os.path.join(DATA_DIR, "metrics.json"))
    return data or []


METRIC_REPO_EXCLUDED = (
    "id",
    "username",
    "created_at",
    "installs",
    "revenue",
    "active_users",
    "sessions",
    "avg_session_duration",
    "retention_1d",
    "retention_7d",
    "retention_30d",
)

COMMENT_REPO_EXCLUDED = (
    "id",
    "username",
    "created_at",
    "review_id",
    "rating",
    "title",
    "content",
    "author",
    "date",
    "helpful_count",
    "sentiment",
)


def _normalize_export_value(key: str, value: Any) -> Any:
    if key == "值" and isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def _strip_repo_fields(records: List[Dict], excluded_keys: Tuple[str, ...]) -> List[Dict]:
    filtered: List[Dict] = []
    for record in records:
        filtered_record = {
            key: _normalize_export_value(key, value)
            for key, value in record.items()
            if key not in excluded_keys
            and value is not None
            and value != ""
            and value not in (0, 0.0)
        }
        filtered.append(filtered_record)
    return filtered


def _product_ids_in_records(records: List[Dict]) -> set:
    return {record_product(row) for row in records if record_product(row)}


def comments_dataset_usable(records: List[Dict[str, Any]]) -> bool:
    if not records:
        return False
    products = _product_ids_in_records(records)
    if not products or products <= TEST_ONLY_PRODUCTS:
        return False
    return True


def cached_metrics_usable(records: List[Dict[str, Any]]) -> bool:
    if not records:
        return False
    if metrics_dataset_usable(records):
        return True
    products = _product_ids_in_records(records)
    return bool(products - TEST_ONLY_PRODUCTS)


def resolve_user_data_source(username: str) -> str:
    if ImportedDataRepository.get_comments(username) or ImportedDataRepository.get_metrics(username):
        return "imported"
    _, _, mvp_source = get_mvp_comments_and_metrics(resolve_mvp_output_dir(username))
    if mvp_source:
        return mvp_source
    cached_metrics = ImportedDataRepository.get_cached_metrics(max_age_hours=24)
    cached_comments = ImportedDataRepository.get_cached_comments(max_age_hours=24)
    if (cached_comments and comments_dataset_usable(cached_comments)) or (
        cached_metrics and cached_metrics_usable(cached_metrics)
    ):
        return "cached"
    return "empty"


def get_user_comments_data(username: str) -> List[Dict]:
    imported = ImportedDataRepository.get_comments(username)
    if imported:
        return _strip_repo_fields(imported, COMMENT_REPO_EXCLUDED)

    mvp_comments, _, mvp_source = get_mvp_comments_and_metrics(resolve_mvp_output_dir(username))
    if mvp_source and mvp_comments:
        return mvp_comments

    cached = ImportedDataRepository.get_cached_comments(max_age_hours=24)
    if cached and comments_dataset_usable(cached):
        return _strip_repo_fields(cached, ("id", "cached_at"))

    return []


def get_user_metrics_data(username: str) -> List[Dict]:
    imported = ImportedDataRepository.get_metrics(username)
    if imported:
        return _strip_repo_fields(imported, METRIC_REPO_EXCLUDED)

    _, mvp_metrics, mvp_source = get_mvp_comments_and_metrics(resolve_mvp_output_dir(username))
    if mvp_source and mvp_metrics:
        return mvp_metrics

    cached = ImportedDataRepository.get_cached_metrics(max_age_hours=24)
    if cached and cached_metrics_usable(cached):
        return _strip_repo_fields(cached, ("id", "cached_at"))

    return []

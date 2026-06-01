"""Load and validate persisted MVP Steam artifacts."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional, Tuple  # noqa: F401 — Any used by normalize_product_id

from src.mvp_pipeline import DEFAULT_OUTPUT_DIR

ARTIFACT_FILES = {
    "dataset": "steam_dataset.json",
    "analysis": "analysis.json",
    "validation": "validation.json",
}


def resolve_output_dir(output_dir: Optional[str] = None) -> str:
    return os.path.abspath(output_dir or DEFAULT_OUTPUT_DIR)


def artifact_path(name: str, output_dir: Optional[str] = None) -> str:
    filename = ARTIFACT_FILES.get(name)
    if not filename:
        raise ValueError(f"Unknown MVP artifact: {name}")
    return os.path.join(resolve_output_dir(output_dir), filename)


def load_mvp_artifact(name: str, output_dir: Optional[str] = None) -> Optional[Dict[str, Any]]:
    path = artifact_path(name, output_dir)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def mvp_validation_passed(output_dir: Optional[str] = None) -> bool:
    validation = load_mvp_artifact("validation", output_dir)
    return bool(validation and validation.get("passed"))


def get_mvp_dataset(output_dir: Optional[str] = None) -> Optional[Dict[str, Any]]:
    if not mvp_validation_passed(output_dir):
        return None
    return load_mvp_artifact("dataset", output_dir)


def get_mvp_analysis(output_dir: Optional[str] = None) -> Optional[Dict[str, Any]]:
    if not mvp_validation_passed(output_dir):
        return None
    return load_mvp_artifact("analysis", output_dir)


def get_mvp_comments_and_metrics(
    output_dir: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Optional[str]]:
    dataset = get_mvp_dataset(output_dir)
    if not dataset:
        return [], [], None
    comments = list(dataset.get("comments") or [])
    metrics = list(dataset.get("metrics") or [])
    source = str(dataset.get("source") or dataset.get("data_source") or "").strip()
    if not source:
        platforms = {
            str(row.get("platform") or row.get("平台") or row.get("channel") or "").lower()
            for row in metrics
        }
        platforms.discard("")
        if platforms == {"taptap"}:
            source = "taptap_public"
        elif platforms == {"google play"}:
            source = "google_play_public"
        elif len(platforms) > 1:
            source = "mvp_multi"
        elif "taptap" in platforms:
            source = "mvp_multi"
        elif "google play" in platforms:
            source = "mvp_multi"
        else:
            source = "mvp_steam"
    return comments, metrics, source


def normalize_product_id(value: Any) -> str:
    if value is None:
        return ""
    product_id = str(value).strip()
    if product_id.startswith("steam_") and product_id[6:].isdigit():
        return product_id[6:]
    return product_id


def record_product(record: Dict[str, Any]) -> str:
    for key in ("product", "产品", "app_id", "steam_app_id"):
        raw = record.get(key)
        if raw not in (None, ""):
            return normalize_product_id(raw)
    return ""


def product_matches(record: Dict[str, Any], target: str) -> bool:
    if not target or target == "all":
        return True
    pid = record_product(record)
    if not pid:
        return False
    if pid == target or str(pid) == str(target):
        return True
    return False


def normalize_time_period(period: Optional[str]) -> Optional[str]:
    if not period or period == "all":
        return None
    key = period.lower().replace("_", " ").replace("-", " ").strip()
    aliases = {
        "week 20": "week_20",
        "week20": "week_20",
        "week 21": "week_21",
        "week21": "week_21",
        "week 22": "week_22",
        "week22": "week_22",
        "q2": "q2",
        "quarter 2": "q2",
        "quarter2": "q2",
        "month 4": "month_4",
        "month4": "month_4",
        "month 5": "month_5",
        "month5": "month_5",
    }
    return aliases.get(key, period.lower())


def metric_matches_period(metric: Dict[str, Any], period: Optional[str]) -> bool:
    if not period or period == "all":
        return True
    cycle_raw = str(metric.get("cycle") or metric.get("周期") or "").strip()
    if not cycle_raw:
        return True
    if cycle_raw == period or cycle_raw.lower() == period.lower():
        return True
    normalized = normalize_time_period(period)
    cycle_key = cycle_raw.lower().replace("_", " ").replace("-", " ").strip()
    cycle_compact = cycle_key.replace(" ", "")

    candidates = {normalized, period.lower()}
    if normalized == "week_20":
        candidates.update({"week 20", "week20"})
    elif normalized == "week_21":
        candidates.update({"week 21", "week21"})
    elif normalized == "week_22":
        candidates.update({"week 22", "week22"})
    elif normalized == "q2":
        candidates.update({"q2", "quarter 2", "quarter_2"})
    elif normalized and normalized.startswith("month_"):
        candidates.add(normalized.replace("_", " "))

    for candidate in candidates:
        if not candidate:
            continue
        cand = candidate.lower().replace("_", " ").strip()
        cand_compact = cand.replace(" ", "")
        if cycle_key == cand or cycle_compact == cand_compact:
            return True
        if cand in cycle_key or cand_compact in cycle_compact:
            return True
    if str(metric.get("date", "")).startswith(period[:4]):
        return True
    return False


def comment_matches_period(comment: Dict[str, Any], period: Optional[str]) -> bool:
    if not period:
        return True
    cycle = str(comment.get("cycle") or comment.get("周期") or "")
    if cycle and metric_matches_period({"cycle": cycle}, period):
        return True
    date_value = str(comment.get("date") or comment.get("日期") or "")
    normalized = normalize_time_period(period) or period
    if normalized and normalized.startswith("month_"):
        month_num = normalized.split("_", 1)[-1]
        if month_num and f"-{month_num.zfill(2)}-" in date_value:
            return True
    if normalized in {"week_20", "week_21", "week_22"} and date_value:
        return True
    return not cycle


def filter_records(
    comments: List[Dict[str, Any]],
    metrics: List[Dict[str, Any]],
    *,
    product: Optional[str] = None,
    products: Optional[List[str]] = None,
    data_source: Optional[str] = None,
    time_period: Optional[str] = None,
    platform: Optional[str] = None,
    sentiment: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    filtered_comments = list(comments)
    filtered_metrics = list(metrics)

    if products:
        product_set = {normalize_product_id(p) for p in products if p and p != "all"}
        filtered_comments = [c for c in filtered_comments if record_product(c) in product_set]
        filtered_metrics = [m for m in filtered_metrics if record_product(m) in product_set]
    elif product and product != "all":
        filtered_comments = [c for c in filtered_comments if product_matches(c, product)]
        filtered_metrics = [m for m in filtered_metrics if product_matches(m, product)]

    source = platform or data_source
    if source and source != "all":
        source_lower = source.replace("_", " ").lower()
        filtered_comments = [
            c
            for c in filtered_comments
            if c.get("platform", "").lower() == source_lower
            or c.get("channel", "").lower() == source_lower
            or c.get("平台", "").lower() == source_lower
        ]
        filtered_metrics = [
            m
            for m in filtered_metrics
            if m.get("platform", "").lower() == source_lower
            or m.get("channel", "").lower() == source_lower
            or m.get("平台", "").lower() == source_lower
        ]

    if time_period and time_period != "all":
        filtered_metrics = [m for m in filtered_metrics if metric_matches_period(m, time_period)]
        filtered_comments = [c for c in filtered_comments if comment_matches_period(c, time_period)]

    if sentiment and sentiment != "all":
        sentiment_map = {
            "positive": {"positive", "正面"},
            "neutral": {"neutral", "中性"},
            "negative": {"negative", "负面"},
        }
        allowed = sentiment_map.get(sentiment, {sentiment})
        filtered_comments = [
            c for c in filtered_comments if str(c.get("情绪") or c.get("sentiment") or "") in allowed
        ]

    return filtered_comments, filtered_metrics


def build_mvp_report_payload(
    comments: List[Dict[str, Any]],
    metrics: List[Dict[str, Any]],
    output_dir: Optional[str] = None,
) -> Dict[str, Any]:
    from src.mvp_pipeline import analyze_actual_steam_data

    full_analysis = get_mvp_analysis(output_dir)
    if not comments and not metrics and full_analysis:
        return {
            "mode": "mvp_steam",
            "validation_passed": True,
            "summary": full_analysis.get("summary"),
            "product_reports": full_analysis.get("product_reports", []),
            "ai_strategy": full_analysis.get("ai_strategy"),
        }

    analysis = analyze_actual_steam_data(comments, metrics)
    return {
        "mode": "mvp_steam",
        "validation_passed": mvp_validation_passed(output_dir),
        "summary": analysis.get("summary"),
        "product_reports": analysis.get("product_reports", []),
        "ai_strategy": analysis.get("ai_strategy"),
    }

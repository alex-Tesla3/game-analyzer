"""Realtime and cohort analytics from crawled reviews or imported owner metrics."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

from src.mvp_data import product_matches
from src.services.engagement_funnel import (
    _comments_for_product,
    _is_positive_comment,
    _metrics_for_product,
    _parse_numeric,
    _playtime_minutes,
    _comment_score,
    _comment_text,
    MIN_REVIEW_SAMPLE,
)

COHORT_REVIEW_MIN = 8


def _metric_scalar(row: Dict[str, Any]) -> float:
    return _parse_numeric(row.get("值") if row.get("值") is not None else row.get("value"))


def _comment_date(comment: Dict[str, Any]) -> str:
    for key in ("日期", "date", "review_date", "created_at"):
        raw = comment.get(key)
        if not raw:
            continue
        text = str(raw).strip()
        if len(text) >= 10:
            return text[:10]
    return ""


def _week_key(date_text: str) -> str:
    try:
        dt = datetime.strptime(date_text[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        year, week, _ = dt.isocalendar()
        return f"{year}-W{week:02d}"
    except ValueError:
        return "未知周期"


def _sum_metric_values(
    metrics: Sequence[Dict[str, Any]],
    *,
    exact: Sequence[str] = (),
    contains: Sequence[str] = (),
) -> Tuple[float, int]:
    total = 0.0
    count = 0
    for row in metrics:
        name = str(row.get("metric") or "")
        if name in exact or any(token in name for token in contains):
            total += _metric_scalar(row)
            count += 1
    return total, count


def _weekly_review_trend(comments: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    buckets: Dict[str, int] = defaultdict(int)
    for row in comments:
        date_text = _comment_date(row)
        if not date_text:
            continue
        buckets[_week_key(date_text)] += 1
    if not buckets:
        return []
    ordered = sorted(buckets.items())[-8:]
    return [
        {"time": label, "value": count, "is_current": index == len(ordered) - 1}
        for index, (label, count) in enumerate(ordered)
    ]


def _try_imported_cohort(
    product_id: str,
    metrics: Sequence[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    rows = _metrics_for_product(metrics, product_id)
    if not rows:
        return None

    installs = max(int(row.get("installs") or 0) for row in rows)
    r1 = max(_parse_numeric(row.get("retention_1d")) for row in rows)
    r7 = max(_parse_numeric(row.get("retention_7d")) for row in rows)
    r30 = max(_parse_numeric(row.get("retention_30d")) for row in rows)
    if installs <= 0 or (r1 <= 0 and r7 <= 0 and r30 <= 0):
        return None

    cohorts = [
        {
            "cohort_week": "导入快照",
            "initial_users": installs,
            "retention_d1": round(r1, 1),
            "retention_d7": round(r7, 1),
            "retention_d30": round(r30, 1),
            "revenue_per_user": 0.0,
            "arppu": 0.0,
        }
    ]
    revenue_total, revenue_count = _sum_metric_values(rows, contains=("收入", "revenue", "arpu"))
    if revenue_count:
        cohorts[0]["revenue_per_user"] = round(revenue_total / revenue_count, 2)

    summary = {
        "best_retention_cohort": "导入快照",
        "avg_retention_d7": r7,
        "avg_revenue_per_user": cohorts[0]["revenue_per_user"],
        "health_score": 80 if r7 >= 25 else 65 if r7 >= 15 else 50,
        "cohort_mode": "imported_retention",
        "metric_labels": {
            "retention_d1": "次日留存",
            "retention_d7": "7日留存",
            "retention_d30": "30日留存",
        },
        "data_note": "基于导入指标中的 installs 与 retention 字段。",
    }
    summary["improvements"] = _cohort_improvements(cohorts, summary)
    return {
        "cohorts": cohorts,
        "retention_matrix": _retention_matrix(cohorts),
        "summary": summary,
        "data_basis": "imported_retention",
        "data_note": summary["data_note"],
    }


def _retention_matrix(cohorts: Sequence[Dict[str, Any]]) -> List[List[Any]]:
    header = ["群组", "初始用户", "D1", "D7", "D30"]
    body = [
        [
            row["cohort_week"],
            row["initial_users"],
            f"{row['retention_d1']}%",
            f"{row['retention_d7']}%",
            f"{row['retention_d30']}%",
        ]
        for row in cohorts
    ]
    return [header] + body


def _cohort_improvements(cohorts: Sequence[Dict[str, Any]], summary: Dict[str, Any]) -> List[Dict[str, str]]:
    avg_d7 = float(summary.get("avg_retention_d7") or 0)
    if avg_d7 < 20:
        return [
            {
                "priority": "high",
                "area": "留存 / 参与",
                "suggestion": f"7日维度指标仅 {avg_d7:.1f}%，建议结合评论主题与版本节奏排查流失点。",
            }
        ]
    return [
        {
            "priority": "info",
            "area": "整体",
            "suggestion": "群组指标整体平稳，建议持续对比各周样本波动。",
        }
    ]


def build_review_weekly_cohort(
    product_id: str,
    comments: Sequence[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    rows = _comments_for_product(comments, product_id)
    dated = [row for row in rows if _comment_date(row)]
    if len(dated) < COHORT_REVIEW_MIN:
        return None

    buckets: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in dated:
        buckets[_week_key(_comment_date(row))].append(row)

    ordered_weeks = sorted(buckets.items())[-6:]
    cohorts: List[Dict[str, Any]] = []
    for week_label, week_rows in ordered_weeks:
        total = len(week_rows)
        positive = sum(1 for row in week_rows if _is_positive_comment(row))
        high_score = sum(1 for row in week_rows if _comment_score(row) >= 4)
        engaged = sum(
            1
            for row in week_rows
            if _playtime_minutes(row) >= 1200 or len(_comment_text(row)) >= 20
        )
        cohorts.append(
            {
                "cohort_week": week_label,
                "initial_users": total,
                "retention_d1": round(positive / total * 100, 1) if total else 0.0,
                "retention_d7": round(high_score / total * 100, 1) if total else 0.0,
                "retention_d30": round(engaged / total * 100, 1) if total else 0.0,
                "revenue_per_user": 0.0,
                "arppu": 0.0,
            }
        )

    if not cohorts:
        return None

    avg_d7 = sum(row["retention_d7"] for row in cohorts) / len(cohorts)
    best = max(cohorts, key=lambda row: row["retention_d7"])["cohort_week"]
    summary = {
        "best_retention_cohort": best,
        "avg_retention_d7": avg_d7,
        "avg_revenue_per_user": 0.0,
        "health_score": 78 if avg_d7 >= 55 else 62 if avg_d7 >= 40 else 48,
        "cohort_mode": "review_weekly",
        "metric_labels": {
            "retention_d1": "正面评价率",
            "retention_d7": "中高分(≥4星)占比",
            "retention_d30": "深度参与率",
        },
        "data_note": "按评论发布周分组；指标为样本参与度代理，非 DAU 留存。",
    }
    summary["improvements"] = _cohort_improvements(cohorts, summary)
    return {
        "cohorts": cohorts,
        "retention_matrix": _retention_matrix(cohorts),
        "summary": summary,
        "data_basis": "review_weekly",
        "data_note": summary["data_note"],
    }


def build_realtime_from_data(
    product_id: str,
    comments: Sequence[Dict[str, Any]],
    metrics: Sequence[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    scoped_comments = (
        _comments_for_product(comments, product_id)
        if product_id and product_id != "all"
        else list(comments)
    )
    scoped_metrics = (
        _metrics_for_product(metrics, product_id)
        if product_id and product_id != "all"
        else list(metrics)
    )

    sample_count = len(scoped_comments)
    downloads, _ = _sum_metric_values(scoped_metrics, exact=("用户总下载量",), contains=("抓取评论数", "Steam汇总评论数", "评论数"))
    if not sample_count and not downloads:
        return None

    if not sample_count and downloads:
        sample_count = int(downloads)

    positive = sum(1 for row in scoped_comments if _is_positive_comment(row)) if scoped_comments else 0
    positive_rate = round(positive / sample_count * 100, 1) if sample_count and scoped_comments else None
    if positive_rate is None:
        rate_total, rate_count = _sum_metric_values(scoped_metrics, contains=("好评率", "评分", "rating"))
        if rate_count:
            positive_rate = round(rate_total / rate_count, 1)

    arppu_total, arppu_count = _sum_metric_values(scoped_metrics, contains=("ARPPU", "当前价格", "price"))
    avg_arppu = round(arppu_total / arppu_count / (100.0 if "价格" in str(scoped_metrics) else 1.0), 2) if arppu_count else 0.0

    trend = _weekly_review_trend(scoped_comments)
    has_real_trend = bool(trend)
    basis = "review_sample" if scoped_comments else "imported_metrics"

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data_basis": basis,
        "data_note": (
            "评论样本、按周评论量与好评率为真实抓取数据；在线用户与收入为演示占位，仅供布局展示。"
            if scoped_comments
            else "规模指标来自导入/抓取汇总；收入曲线为演示占位。"
        ),
        "simulated_fields": ["online_users", "today_revenue", "estimated_daily_revenue", "current_hour_revenue"],
        "online_users": None,
        "today_revenue": None,
        "estimated_daily_revenue": None,
        "current_hour_revenue": None,
        "hours_passed": datetime.now().hour + 1,
        "total_downloads": int(downloads or sample_count),
        "review_sample_count": sample_count,
        "avg_arppu": avg_arppu,
        "steam_positive_rate": positive_rate,
        "positive_rate": positive_rate,
        "revenue_trend": trend if has_real_trend else [],
        "chart_label": "按周评论量（真实样本）" if has_real_trend else "暂无时间分布样本",
        "chart_metric": "reviews",
        "data_explanation": (
            f"评论样本 {sample_count} 条"
            + (f" · 好评率 {positive_rate}%" if positive_rate is not None else "")
            + " · 下图按评论发布周统计"
            if scoped_comments
            else f"指标样本 {int(downloads or 0)} · 请导入 Owner 收入数据以替换演示 KPI"
        ),
    }


def resolve_cohort_for_product(
    product_id: str,
    comments: Sequence[Dict[str, Any]],
    metrics: Sequence[Dict[str, Any]],
) -> Tuple[Optional[Dict[str, Any]], str, bool]:
    imported = _try_imported_cohort(product_id, metrics)
    if imported:
        return imported, "imported_retention", False
    cohort = build_review_weekly_cohort(product_id, comments)
    if cohort:
        return cohort, "review_weekly", False
    return None, "mock_data", True


def resolve_realtime_for_product(
    product_id: str,
    comments: Sequence[Dict[str, Any]],
    metrics: Sequence[Dict[str, Any]],
) -> Tuple[Optional[Dict[str, Any]], str, bool]:
    payload = build_realtime_from_data(product_id, comments, metrics)
    if payload:
        return payload, str(payload.get("data_basis") or "review_sample"), False
    return None, "mock_data", True


def data_basis_label(basis: str) -> str:
    labels = {
        "review_sample": "真实评论样本 · 按周评论量",
        "imported_metrics": "真实导入指标",
        "imported_retention": "真实导入指标 · 留存群组",
        "review_weekly": "真实评论样本 · 按周群组",
        "mock_data": "演示模板",
    }
    return labels.get(basis, basis)

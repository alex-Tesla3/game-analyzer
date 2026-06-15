"""Journey and funnel analytics derived from imported metrics or crawled reviews."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from src.mvp_data import product_matches

FUNNEL_METRIC_PATTERNS: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("下载", ("下载", "download", "install", "安装")),
    ("注册", ("注册", "register", "新增用户", "new user", "dau", "活跃")),
    ("完成新手教程", ("教程", "tutorial", "新手", "引导")),
    ("首次战斗", ("战斗", "battle", "首局", "对局")),
    ("首次充值", ("充值", "付费", "purchase", "paying", "pay ", "内购")),
)

MIN_REVIEW_SAMPLE = 5


def _parse_numeric(value: Any) -> float:
    if value is None or value == "":
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "").replace("¥", "").replace("%", "")
    try:
        return float(text)
    except ValueError:
        return 0.0


def _metric_scalar(row: Dict[str, Any]) -> float:
    return _parse_numeric(row.get("值") if row.get("值") is not None else row.get("value"))


def _comments_for_product(comments: Sequence[Dict[str, Any]], product_id: str) -> List[Dict[str, Any]]:
    return [row for row in comments if product_matches(row, product_id)]


def _metrics_for_product(metrics: Sequence[Dict[str, Any]], product_id: str) -> List[Dict[str, Any]]:
    return [row for row in metrics if product_matches(row, product_id)]


def _is_positive_comment(comment: Dict[str, Any]) -> bool:
    mood = str(comment.get("情绪") or comment.get("sentiment") or "").strip().lower()
    if mood in {"positive", "正面", "积极", "好评"}:
        return True
    if mood in {"negative", "负面", "消极", "差评"}:
        return False
    if "voted_up" in comment:
        return bool(comment.get("voted_up"))
    if "thumbsUp" in comment:
        return bool(comment.get("thumbsUp"))
    score = _parse_numeric(comment.get("rating") or comment.get("score") or 0)
    return score >= 4


def _comment_score(comment: Dict[str, Any]) -> float:
    return _parse_numeric(comment.get("rating") or comment.get("score") or 0)


def _playtime_minutes(comment: Dict[str, Any]) -> int:
    return int(comment.get("playtime_forever_minutes") or 0)


def _recent_playtime_minutes(comment: Dict[str, Any]) -> int:
    return int(comment.get("playtime_last_two_weeks_minutes") or 0)


def _comment_text(comment: Dict[str, Any]) -> str:
    return str(comment.get("内容") or comment.get("content") or "").strip()


def _has_playtime_signal(comments: Sequence[Dict[str, Any]]) -> bool:
    return any(_playtime_minutes(row) > 0 for row in comments)


def _build_step_nodes(
    steps: Sequence[Tuple[str, int, str]],
    *,
    basis: str,
    note: str,
) -> Dict[str, Any]:
    nodes: List[Dict[str, Any]] = []
    for index, (name, count, step_type) in enumerate(steps):
        node: Dict[str, Any] = {
            "id": f"step_{index}",
            "name": name,
            "count": int(count),
            "type": step_type,
        }
        if index > 0 and steps[index - 1][1] > 0:
            node["conversion_rate"] = round(count / steps[index - 1][1] * 100, 1)
        nodes.append(node)

    base = steps[0][1] if steps else 0
    final = steps[-1][1] if steps else 0
    dropoffs = _identify_step_dropoffs(steps)

    return {
        "nodes": nodes,
        "edges": [],
        "summary": {
            "total_users": base,
            "final_conversion_rate": round(final / base * 100, 1) if base else 0.0,
            "high_dropoff_points": dropoffs,
            "journey_nodes": nodes,
            "data_basis": basis,
            "data_note": note,
        },
    }


def _identify_step_dropoffs(steps: Sequence[Tuple[str, int, str]]) -> List[Dict[str, Any]]:
    points: List[Dict[str, Any]] = []
    for index in range(1, len(steps)):
        prev_name, prev_count, _ = steps[index - 1]
        name, count, _ = steps[index]
        if prev_count <= 0:
            continue
        lost = prev_count - count
        if lost <= 0:
            continue
        rate = round(lost / prev_count * 100, 1)
        if rate >= 15:
            points.append(
                {
                    "node": f"step_{index - 1}",
                    "node_name": prev_name,
                    "count": lost,
                    "rate": rate,
                    "severity": "high" if rate >= 30 else "medium",
                    "next_step": name,
                }
            )
    return sorted(points, key=lambda item: item["count"], reverse=True)[:4]


def build_review_engagement_journey(
    product_id: str,
    comments: Sequence[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    rows = _comments_for_product(comments, product_id)
    if len(rows) < MIN_REVIEW_SAMPLE:
        return None

    if _has_playtime_signal(rows):
        total = len(rows)
        with_playtime = sum(1 for row in rows if _playtime_minutes(row) > 0)
        recent_active = sum(1 for row in rows if _recent_playtime_minutes(row) > 0)
        core_players = sum(1 for row in rows if _playtime_minutes(row) >= 1200)
        deep_players = sum(1 for row in rows if _playtime_minutes(row) >= 6000)
        positive = sum(1 for row in rows if _is_positive_comment(row))
        steps = [
            ("评论样本", total, "start"),
            ("有游玩时长", with_playtime, "normal"),
            ("近两周仍活跃", recent_active, "normal"),
            ("核心玩家(≥20h)", core_players, "normal"),
            ("深度玩家(≥100h)", deep_players, "normal"),
            ("正面评价", positive, "conversion"),
        ]
        note = "基于 Steam 抓取评论的游玩时长与推荐/情绪分布计算，各游戏样本量与结构不同，转化率会不同。"
    else:
        total = len(rows)
        rated = sum(1 for row in rows if _comment_score(row) >= 1)
        high_score = sum(1 for row in rows if _comment_score(row) >= 4)
        detailed = sum(1 for row in rows if len(_comment_text(row)) >= 20)
        positive = sum(1 for row in rows if _is_positive_comment(row))
        steps = [
            ("评论样本", total, "start"),
            ("有效评分", rated, "normal"),
            ("中高分(≥4星)", high_score, "normal"),
            ("详评(≥20字)", detailed, "normal"),
            ("正面评价", positive, "conversion"),
        ]
        note = "基于 TapTap / Google Play 抓取评论的评分与文本长度计算，各游戏评论结构不同，转化率会不同。"

    return _build_step_nodes(steps, basis="review_engagement", note=note)


def _funnel_steps_from_counts(
    ordered: Sequence[Tuple[str, int]],
) -> List[Dict[str, Any]]:
    if not ordered:
        return []
    top = ordered[0][1] or 1
    steps: List[Dict[str, Any]] = []
    for index, (label, count) in enumerate(ordered):
        prev = ordered[index - 1][1] if index > 0 else count
        prev = prev or 1
        steps.append(
            {
                "step": label,
                "count": int(count),
                "conversion_from_top": round(count / top * 100, 1),
                "conversion_from_prev": round(count / prev * 100, 1) if index > 0 else 100.0,
            }
        )
    return steps


def _try_retention_metric_funnel(
    product_id: str,
    metrics: Sequence[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    rows = _metrics_for_product(metrics, product_id)
    if not rows:
        return None

    installs = max(int(row.get("installs") or 0) for row in rows)
    if installs <= 0:
        return None

    r1 = max(_parse_numeric(row.get("retention_1d")) for row in rows)
    r7 = max(_parse_numeric(row.get("retention_7d")) for row in rows)
    r30 = max(_parse_numeric(row.get("retention_30d")) for row in rows)
    active_users = max(int(row.get("active_users") or 0) for row in rows)
    if r1 <= 0 and r7 <= 0 and r30 <= 0 and active_users <= 0:
        return None

    day1 = int(installs * r1 / 100) if r1 > 0 else active_users
    day7 = int(installs * r7 / 100) if r7 > 0 else int(day1 * 0.7)
    day30 = int(installs * r30 / 100) if r30 > 0 else int(day7 * 0.6)
    paying_metric = 0.0
    for row in rows:
        name = str(row.get("metric") or "").lower()
        if any(token in name for token in ("付费", "paying", "purchase", "充值")):
            paying_metric = max(paying_metric, _metric_scalar(row))
    paying_users = int(paying_metric) if paying_metric > 0 else max(1, int(day30 * 0.08))

    ordered = [
        ("安装", installs),
        ("次日留存", max(day1, 0)),
        ("7日留存", max(day7, 0)),
        ("30日留存", max(day30, 0)),
        ("付费用户", max(paying_users, 0)),
    ]
    steps = _funnel_steps_from_counts(ordered)
    return _format_funnel_payload(
        steps,
        basis="imported_retention",
        note="基于导入指标中的 installs 与 retention 字段计算。",
        health_score=_health_from_steps(steps),
    )


def _try_named_metric_funnel(
    product_id: str,
    metrics: Sequence[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    rows = _metrics_for_product(metrics, product_id)
    if not rows:
        return None

    values: Dict[str, float] = {}
    for row in rows:
        name = str(row.get("metric") or "").lower()
        amount = _metric_scalar(row)
        if amount <= 0:
            continue
        for label, patterns in FUNNEL_METRIC_PATTERNS:
            if any(pattern in name for pattern in patterns):
                values[label] = max(values.get(label, 0.0), amount)

    ordered_labels = [label for label, _ in FUNNEL_METRIC_PATTERNS if label in values]
    if len(ordered_labels) < 3:
        return None

    ordered = [(label, int(values[label])) for label in ordered_labels]
    steps = _funnel_steps_from_counts(ordered)
    return _format_funnel_payload(
        steps,
        basis="imported_metrics",
        note="基于导入 CSV 中漏斗相关指标名（下载/注册/教程/战斗/付费）计算。",
        health_score=_health_from_steps(steps),
    )


def _health_from_steps(steps: Sequence[Dict[str, Any]]) -> int:
    if len(steps) < 2:
        return 60
    prev_rates = [step.get("conversion_from_prev", 100) for step in steps[1:]]
    avg_prev = sum(prev_rates) / len(prev_rates)
    if avg_prev >= 70:
        return 85
    if avg_prev >= 50:
        return 72
    if avg_prev >= 35:
        return 58
    return 45


def _funnel_recommendations(steps: Sequence[Dict[str, Any]]) -> List[Dict[str, str]]:
    recs: List[Dict[str, str]] = []
    for step in steps[1:]:
        rate = float(step.get("conversion_from_prev") or 0)
        if rate < 25:
            recs.append(
                {
                    "type": "critical",
                    "step": step["step"],
                    "suggestion": f"{step['step']} 环节转化率仅 {rate}%，建议优先排查该步骤流失原因。",
                }
            )
        elif rate < 50:
            recs.append(
                {
                    "type": "warning",
                    "step": step["step"],
                    "suggestion": f"{step['step']} 转化率 {rate}% 偏低，可针对该环节做 A/B 或体验优化。",
                }
            )
    if not recs:
        recs.append(
            {
                "type": "info",
                "step": "整体",
                "suggestion": "转化链路整体平稳，建议持续监控各步骤波动。",
            }
        )
    return recs[:4]


def _format_funnel_payload(
    steps: Sequence[Dict[str, Any]],
    *,
    basis: str,
    note: str,
    health_score: int,
) -> Dict[str, Any]:
    top = steps[0]["count"] if steps else 0
    bottom = steps[-1]["count"] if steps else 0
    return {
        "steps": list(steps),
        "total_conversion_rate": round(bottom / top * 100, 1) if top else 0.0,
        "health_score": health_score,
        "recommendations": _funnel_recommendations(steps),
        "health_improvements": _funnel_recommendations(steps),
        "high_dropoff_steps": [
            {
                "step": steps[index]["step"],
                "dropoff_rate": round(
                    100 - float(steps[index].get("conversion_from_prev") or 0),
                    1,
                ),
            }
            for index in range(1, len(steps))
            if float(steps[index].get("conversion_from_prev") or 100) < 60
        ],
        "data_basis": basis,
        "data_note": note,
    }


def build_review_engagement_funnel(
    product_id: str,
    comments: Sequence[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    journey = build_review_engagement_journey(product_id, comments)
    if not journey:
        return None
    steps = _funnel_steps_from_counts(
        [(node["name"], node["count"]) for node in journey["nodes"]]
    )
    return _format_funnel_payload(
        steps,
        basis="review_engagement",
        note=journey["summary"]["data_note"],
        health_score=_health_from_steps(steps),
    )


def build_metric_funnel(
    product_id: str,
    metrics: Sequence[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    retention = _try_retention_metric_funnel(product_id, metrics)
    if retention:
        return retention
    return _try_named_metric_funnel(product_id, metrics)


def build_path_distribution_from_comments(
    product_id: str,
    comments: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    rows = _comments_for_product(comments, product_id)
    if not rows:
        return []

    if _has_playtime_signal(rows):
        full_path = sum(
            1
            for row in rows
            if _playtime_minutes(row) >= 1200 and _is_positive_comment(row)
        )
        play_positive = sum(
            1
            for row in rows
            if _playtime_minutes(row) > 0 and _is_positive_comment(row)
        )
        play_negative = sum(
            1
            for row in rows
            if _playtime_minutes(row) > 0 and not _is_positive_comment(row)
        )
        no_play_negative = sum(
            1
            for row in rows
            if _playtime_minutes(row) <= 0 and not _is_positive_comment(row)
        )
        return [
            {
                "path": "样本→核心游玩→正面评价",
                "count": full_path,
                "color": "#22c55e",
            },
            {
                "path": "样本→有游玩→正面(非核心)",
                "count": max(play_positive - full_path, 0),
                "color": "#38bdf8",
            },
            {
                "path": "样本→有游玩→负面/不推荐",
                "count": play_negative,
                "color": "#f59e0b",
            },
            {
                "path": "样本→无游玩记录→负面/低分",
                "count": no_play_negative,
                "color": "#ef4444",
            },
        ]

    high_positive = sum(
        1 for row in rows if _comment_score(row) >= 4 and _is_positive_comment(row)
    )
    low_negative = sum(
        1 for row in rows if _comment_score(row) > 0 and not _is_positive_comment(row)
    )
    neutral = max(len(rows) - high_positive - low_negative, 0)
    return [
        {"path": "样本→高分→正面", "count": high_positive, "color": "#22c55e"},
        {"path": "样本→中性/中分", "count": neutral, "color": "#8b5cf6"},
        {"path": "样本→低分→负面", "count": low_negative, "color": "#ef4444"},
    ]


def resolve_journey_for_product(
    product_id: str,
    comments: Sequence[Dict[str, Any]],
    metrics: Sequence[Dict[str, Any]],
) -> Tuple[Optional[Dict[str, Any]], str, bool]:
    journey = build_review_engagement_journey(product_id, comments)
    if journey:
        return journey, "review_engagement", False
    return None, "mock_data", True


def resolve_funnel_for_product(
    product_id: str,
    comments: Sequence[Dict[str, Any]],
    metrics: Sequence[Dict[str, Any]],
) -> Tuple[Optional[Dict[str, Any]], str, bool]:
    funnel = build_metric_funnel(product_id, metrics)
    if funnel:
        return funnel, str(funnel.get("data_basis") or "imported_metrics"), False
    funnel = build_review_engagement_funnel(product_id, comments)
    if funnel:
        return funnel, "review_engagement", False
    return None, "mock_data", True


def data_basis_label(basis: str) -> str:
    labels = {
        "review_engagement": "真实评论样本 · 游玩/评分转化",
        "imported_metrics": "真实导入指标 · 漏斗指标",
        "imported_retention": "真实导入指标 · 留存群组",
        "review_weekly": "真实评论样本 · 按周群组",
        "review_sample": "真实评论样本 · 按周评论量",
        "mixed": "混合数据源",
        "mock_data": "演示模板（无可用真实数据）",
    }
    return labels.get(basis, basis)

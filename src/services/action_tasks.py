"""Action item export and task status helpers."""

from __future__ import annotations

import csv
import io
import json
from typing import Any, Dict, List, Optional

ACTION_STATUSES = ("pending", "in_progress", "done", "verified", "not_met")

STATUS_LABELS = {
    "pending": "待办",
    "in_progress": "进行中",
    "done": "已完成",
    "verified": "已验证",
    "not_met": "未达标",
}


def normalize_action_items(items: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for index, raw in enumerate(items or []):
        if not isinstance(raw, dict):
            continue
        row = dict(raw)
        row.setdefault("id", str(index))
        row.setdefault("status", "pending")
        row.setdefault("verification_note", "")
        out.append(row)
    return out


def actions_to_csv(items: List[Dict[str, Any]]) -> str:
    rows = normalize_action_items(items)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "priority",
            "title",
            "owner_role",
            "action",
            "verify_metric",
            "timeframe",
            "status",
            "verification_note",
            "source",
        ]
    )
    for row in rows:
        writer.writerow(
            [
                row.get("priority", ""),
                row.get("title", ""),
                row.get("owner_role", ""),
                row.get("action", ""),
                row.get("verify_metric", ""),
                row.get("timeframe", ""),
                STATUS_LABELS.get(str(row.get("status") or ""), row.get("status", "")),
                row.get("verification_note", ""),
                row.get("source", ""),
            ]
        )
    return buf.getvalue()


def actions_to_json(items: List[Dict[str, Any]]) -> str:
    return json.dumps(normalize_action_items(items), ensure_ascii=False, indent=2)


_JIRA_PRIORITY = {"P0": "Highest", "P1": "High", "P2": "Medium", "P3": "Low"}


def actions_to_jira_csv(items: List[Dict[str, Any]], project_key: str = "GAME") -> str:
    """CSV importable into Jira (Summary, Priority, Description)."""
    rows = normalize_action_items(items)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Issue Type", "Summary", "Priority", "Description", "Labels"])
    for row in rows:
        priority = str(row.get("priority") or "P2").upper()
        jira_pri = _JIRA_PRIORITY.get(priority, "Medium")
        desc = (
            f"负责人: {row.get('owner_role', '')}\n"
            f"动作: {row.get('action', '')}\n"
            f"验证指标: {row.get('verify_metric', '')}\n"
            f"周期: {row.get('timeframe', '')}\n"
            f"状态: {STATUS_LABELS.get(str(row.get('status') or ''), row.get('status', ''))}\n"
            f"备注: {row.get('verification_note', '')}"
        )
        writer.writerow(
            [
                "Task",
                row.get("title", ""),
                jira_pri,
                desc,
                f"{project_key},{priority}",
            ]
        )
    return buf.getvalue()


def actions_to_feishu_markdown(items: List[Dict[str, Any]], title: str = "可执行行动清单") -> str:
    """Markdown table for Feishu docs / wiki paste."""
    rows = normalize_action_items(items)
    lines = [f"# {title}", "", "| 优先级 | 事项 | 负责人 | 动作 | 验证指标 | 状态 |", "| --- | --- | --- | --- | --- | --- |"]
    for row in rows:
        status = STATUS_LABELS.get(str(row.get("status") or ""), row.get("status", ""))
        cells = [
            str(row.get("priority") or ""),
            str(row.get("title") or "").replace("|", "/"),
            str(row.get("owner_role") or "").replace("|", "/"),
            str(row.get("action") or "").replace("|", "/"),
            str(row.get("verify_metric") or "").replace("|", "/"),
            status,
        ]
        lines.append("| " + " | ".join(cells) + " |")
    lines.append("")
    lines.append("> 粘贴到飞书文档即可；状态可在本系统复盘页同步更新。")
    return "\n".join(lines)


def export_actions_content(items: List[Dict[str, Any]], fmt: str, *, title: str = "actions") -> tuple[str, str, str]:
    """Return (content, media_type, filename_ext)."""
    fmt = (fmt or "csv").lower()
    if fmt == "json":
        return actions_to_json(items), "application/json; charset=utf-8", "json"
    if fmt == "jira":
        return actions_to_jira_csv(items), "text/csv; charset=utf-8", "jira.csv"
    if fmt == "feishu":
        return (
            actions_to_feishu_markdown(items, title=title),
            "text/markdown; charset=utf-8",
            "feishu.md",
        )
    return actions_to_csv(items), "text/csv; charset=utf-8", "csv"


def apply_action_status_updates(
    items: List[Dict[str, Any]],
    updates: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Apply status updates keyed by action id or index."""
    rows = normalize_action_items(items)
    for row in rows:
        key = str(row.get("id", ""))
        patch = updates.get(key)
        if patch is None and key.isdigit():
            patch = updates.get(int(key))
        if not isinstance(patch, dict):
            continue
        if "status" in patch and patch["status"] in ACTION_STATUSES:
            row["status"] = patch["status"]
        if "verification_note" in patch:
            row["verification_note"] = str(patch["verification_note"] or "")
    return rows

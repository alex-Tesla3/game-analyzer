"""Commercial work-guidance summary — analyze → export → retest loop."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from src.services.action_tasks import STATUS_LABELS, normalize_action_items
from src.services.analysis_archive import AnalysisArchiveRepository


def _parse_due_at(item: Dict[str, Any]) -> Optional[str]:
    raw = item.get("due_at")
    if raw:
        return str(raw)[:19]
    tf = str(item.get("timeframe") or "")
    if "本周" in tf:
        return (datetime.now() + timedelta(days=7)).isoformat()[:19]
    if "2 周" in tf or "两周" in tf:
        return (datetime.now() + timedelta(days=14)).isoformat()[:19]
    return None


def _enrich_actions(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    now = datetime.now()
    for row in normalize_action_items(items):
        due = _parse_due_at(row)
        if due and not row.get("due_at"):
            row["due_at"] = due
        if row.get("status") in ("verified", "done"):
            row["overdue"] = False
        elif due:
            try:
                row["overdue"] = datetime.fromisoformat(due[:19]) < now
            except ValueError:
                row["overdue"] = False
        else:
            row["overdue"] = False
        row["status_label"] = STATUS_LABELS.get(str(row.get("status") or ""), row.get("status"))
        out.append(row)
    return out


def work_guidance_summary(username: str) -> Dict[str, Any]:
    archives = AnalysisArchiveRepository.list_for_user(username, limit=10)
    latest_meta = archives[0] if archives else None
    latest = (
        AnalysisArchiveRepository.get(latest_meta["archive_id"], username)
        if latest_meta
        else None
    )
    snap = (latest or {}).get("snapshot_json") or {}
    actions = _enrich_actions(snap.get("action_items") or [])

    pending = sum(1 for a in actions if a.get("status") in ("pending", "in_progress"))
    verified = sum(1 for a in actions if a.get("status") == "verified")
    overdue = sum(1 for a in actions if a.get("overdue"))

    has_retest = bool(snap.get("last_retest_deltas") or snap.get("deltas"))
    has_share = bool(latest and latest.get("share_token"))

    steps: List[Dict[str, Any]] = [
        {
            "id": "analyze",
            "label": "完成竞品分析",
            "detail": "在分析向导输入游戏名，生成报告并自动归档",
            "done": bool(archives),
            "href": "/guide",
        },
        {
            "id": "export",
            "label": "导出行动清单",
            "detail": "CSV / 飞书 / Jira，排进迭代 backlog",
            "done": bool(actions) and pending < len(actions),
            "href": "/work#actions" if actions else "/guide",
        },
        {
            "id": "share",
            "label": "分享给团队",
            "detail": "生成分享链接，团队在协作页查看",
            "done": has_share,
            "href": "/games/review#archives",
        },
        {
            "id": "retest",
            "label": "复测验证（建议 2 周后）",
            "detail": "重新抓取口碑，自动对比好评率并更新验证状态",
            "done": has_retest,
            "href": "/games/review#archives",
        },
    ]

    progress = round(sum(1 for s in steps if s["done"]) / len(steps) * 100) if steps else 0

    return {
        "success": True,
        "progress_pct": progress,
        "steps": steps,
        "latest_archive": {
            "archive_id": latest.get("archive_id") if latest else None,
            "title": latest.get("title") if latest else None,
            "updated_at": latest.get("updated_at") if latest else None,
            "share_token": latest.get("share_token") if latest else None,
            "platform": snap.get("platform"),
        }
        if latest
        else None,
        "action_items": actions,
        "stats": {
            "archives": len(archives),
            "pending": pending,
            "verified": verified,
            "overdue": overdue,
        },
    }

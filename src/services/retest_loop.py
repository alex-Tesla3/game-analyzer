"""Retest loop: re-crawl from archive → compare KPI deltas → verify action items."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence

from src.services.action_tasks import normalize_action_items
from src.services.analysis_archive import AnalysisArchiveRepository
from src.services.analysis_wizard import run_analysis_wizard
from src.services.scenario_ai import archive_scenario_report


def _app_ids_from_archive(archive: Dict[str, Any]) -> List[str]:
    app_ids: List[str] = []
    for gid in archive.get("game_ids") or []:
        token = str(gid)
        if token.startswith("taptap_"):
            pid = token.replace("taptap_", "", 1)
            if pid and pid not in app_ids:
                app_ids.append(pid)
            continue
        if token.startswith("google_play_"):
            pid = token.replace("google_play_", "", 1)
            if pid and pid not in app_ids:
                app_ids.append(pid)
            continue
        if token.startswith("steam_"):
            pid = token.replace("steam_", "", 1)
            if pid.isdigit() and pid not in app_ids:
                app_ids.append(pid)
    if app_ids:
        return app_ids
    for pid in archive.get("product_ids") or []:
        token = str(pid)
        if token.isdigit() and token not in app_ids:
            app_ids.append(token)
    return app_ids


def _platform_from_archive(archive: Dict[str, Any]) -> str:
    snap = archive.get("snapshot_json") or {}
    plat = str(snap.get("platform") or "").lower()
    if plat in ("steam", "taptap", "google_play"):
        return plat
    for gid in archive.get("game_ids") or []:
        if str(gid).startswith("taptap_"):
            return "taptap"
        if str(gid).startswith("google_play_"):
            return "google_play"
    return "steam"


def _baseline_map(archive: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    snap = archive.get("snapshot_json") or {}
    rows = snap.get("baseline_products") or []
    out: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        pid = str(row.get("product") or row.get("product_id") or "")
        if pid:
            out[pid] = row
    if out:
        return out
    for row in snap.get("action_items") or []:
        pass
    for row in (snap.get("facts") or {}).get("products") or []:
        pid = str(row.get("product") or row.get("id") or "")
        if pid:
            out[pid] = row
    return out


def _after_map_from_report(report: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    facts = report.get("facts") or {}
    out: Dict[str, Dict[str, Any]] = {}
    for row in facts.get("products") or []:
        pid = str(row.get("product") or row.get("id") or "")
        gid = str(row.get("game_id") or "")
        if not pid and gid.startswith("steam_"):
            pid = gid.replace("steam_", "", 1)
        elif not pid and gid.startswith("taptap_"):
            pid = gid.replace("taptap_", "", 1)
        elif not pid and gid.startswith("google_play_"):
            pid = gid.replace("google_play_", "", 1)
        if pid:
            out[pid] = row
    return out


def compute_product_deltas(
    before: Dict[str, Dict[str, Any]],
    after: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    products = sorted(set(before) | set(after))
    deltas: List[Dict[str, Any]] = []
    for pid in products:
        b = before.get(pid) or {}
        a = after.get(pid) or {}
        if not b or not a:
            continue
        rate_b = float(b.get("positive_rate") or 0)
        rate_a = float(a.get("positive_rate") or 0)
        deltas.append(
            {
                "product": pid,
                "product_name": a.get("name") or b.get("name") or pid,
                "positive_rate_before": rate_b,
                "positive_rate_after": rate_a,
                "delta": round(rate_a - rate_b, 1),
            }
        )
    deltas.sort(key=lambda x: abs(x.get("delta") or 0), reverse=True)
    return deltas


def verify_action_items(
    action_items: Sequence[Dict[str, Any]],
    deltas: Sequence[Dict[str, Any]],
    *,
    before: Optional[Dict[str, Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Heuristic verification for P0 compare actions based on positive_rate delta."""
    items = normalize_action_items(list(action_items))
    if not deltas:
        return items

    worst_delta = min(deltas, key=lambda d: d.get("delta") or 0)
    best_delta = max(deltas, key=lambda d: d.get("delta") or 0)
    avg_delta = sum(float(d.get("delta") or 0) for d in deltas) / len(deltas)

    for item in items:
        if item.get("status") in ("verified", "not_met", "done"):
            continue
        priority = str(item.get("priority") or "")
        source = str(item.get("source") or "")
        title = str(item.get("title") or "")

        if priority == "P0" and source == "compare":
            target = worst_delta
            delta = float(target.get("delta") or 0)
            name = target.get("product_name") or target.get("product")
            if delta >= 1.0:
                item["status"] = "verified"
                item["verification_note"] = (
                    f"「{name}」样本好评率 +{delta}%"
                    f"（{target['positive_rate_before']}%→{target['positive_rate_after']}%）"
                )
            elif delta >= 0:
                item["status"] = "in_progress"
                item["verification_note"] = f"「{name}」好评率微升 +{delta}%，建议继续观察"
            else:
                item["status"] = "not_met"
                item["verification_note"] = (
                    f"「{name}」好评率 {delta}%"
                    f"（{target['positive_rate_before']}%→{target['positive_rate_after']}%）"
                )
            continue

        if priority == "P1" and source == "scores":
            if avg_delta >= 0.5:
                item["status"] = "verified"
                item["verification_note"] = f"对比产品平均好评率变化 +{avg_delta:.1f}%"
            elif avg_delta >= 0:
                item["status"] = "in_progress"
                item["verification_note"] = f"平均好评率微升 +{avg_delta:.1f}%，建议继续观察"
            else:
                item["status"] = "not_met"
                item["verification_note"] = f"平均好评率下降 {avg_delta:.1f}%"
            continue

        if source == "mvp_signals":
            if avg_delta >= 1.0:
                item["status"] = "verified"
                item["verification_note"] = f"整体口碑提升 +{avg_delta:.1f}%"
            elif avg_delta >= 0:
                item["status"] = "in_progress"
                item["verification_note"] = f"口碑微升 +{avg_delta:.1f}%，继续执行优先行动"
            continue

        if priority == "P2" and source == "compare" and best_delta.get("delta", 0) >= 0:
            item["verification_note"] = (
                f"领先产品「{best_delta.get('product_name')}」当前好评率 "
                f"{best_delta.get('positive_rate_after')}%"
            )

        if before and ("扩大" in title or "样本" in title):
            item["verification_note"] = "复测已完成，请核对评论样本量是否提升"
            if item.get("status") == "pending":
                item["status"] = "in_progress"

    return items


async def retest_from_archive(
    archive_id: str,
    *,
    username: str,
    max_reviews: int = 50,
    auto_archive: bool = True,
) -> Dict[str, Any]:
    archive = AnalysisArchiveRepository.get(archive_id, username)
    if not archive:
        return {"success": False, "message": "归档不存在"}

    app_ids = _app_ids_from_archive(archive)
    platform = _platform_from_archive(archive)
    if not app_ids:
        return {"success": False, "message": "归档缺少产品信息，无法复测"}

    before_map = _baseline_map(archive)
    prior_items = (archive.get("snapshot_json") or {}).get("action_items") or []

    wizard = await run_analysis_wizard(
        app_ids,
        username=username,
        platform=platform,
        max_reviews=max_reviews,
        skip_crawl=False,
        auto_archive=False,
    )
    if not wizard.get("success"):
        return {
            "success": False,
            "message": wizard.get("message") or "复测抓取失败",
            "parent_archive_id": archive_id,
            "steps": wizard.get("steps") or [],
        }

    report = wizard.get("report") or {}
    after_map = _after_map_from_report(report)
    if not before_map and after_map:
        before_map = {
            pid: {"product": pid, "name": row.get("name"), "positive_rate": row.get("positive_rate")}
            for pid, row in after_map.items()
        }

    deltas = compute_product_deltas(before_map, after_map)
    verified_items = verify_action_items(prior_items, deltas, before=before_map)

    retest_snapshot = {
        "retest_of": archive_id,
        "retested_at": datetime.now().isoformat(),
        "baseline_products": [
            {
                "product": pid,
                "name": (before_map.get(pid) or {}).get("name"),
                "positive_rate": (before_map.get(pid) or {}).get("positive_rate"),
            }
            for pid in sorted(before_map)
        ],
        "after_products": [
            {
                "product": pid,
                "name": row.get("name"),
                "positive_rate": row.get("positive_rate"),
            }
            for pid, row in after_map.items()
        ],
        "deltas": deltas,
        "action_items": verified_items,
        "parent_action_items": prior_items,
    }

    new_archive_id = None
    if auto_archive:
        report = dict(report)
        report["action_items"] = verified_items
        report["title"] = (report.get("title") or "复测报告") + " · 复测"
        snap = dict(report.get("facts") or {})
        snap["retest"] = retest_snapshot
        report["facts"] = snap
        new_archive_id = archive_scenario_report(username, report)
        AnalysisArchiveRepository.set_parent_archive(new_archive_id, archive_id, username)
        AnalysisArchiveRepository.merge_snapshot(
            new_archive_id,
            username,
            retest_snapshot,
        )
        AnalysisArchiveRepository.merge_snapshot(
            archive_id,
            username,
            {
                "last_retest_at": retest_snapshot["retested_at"],
                "last_retest_archive_id": new_archive_id,
                "last_retest_deltas": deltas,
                "action_items": verified_items,
            },
        )

    return {
        "success": True,
        "parent_archive_id": archive_id,
        "archive_id": new_archive_id,
        "app_ids": wizard.get("app_ids") or app_ids,
        "deltas": deltas,
        "action_items": verified_items,
        "report": report,
        "steps": wizard.get("steps") or [],
        "compare_url": wizard.get("compare_url"),
    }

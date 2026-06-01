"""Version timeline context for archives and retest reports."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from src.services.game_intel import GameLibraryRepository
from src.services.game_versions import GameVersionRepository


def _parse_date(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    text = str(value).strip()[:19]
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _versions_since(versions: List[Dict[str, Any]], since: Optional[datetime]) -> List[Dict[str, Any]]:
    if not since:
        return versions
    out: List[Dict[str, Any]] = []
    for row in versions:
        released = _parse_date(row.get("released_at") or row.get("created_at"))
        if released is None or released >= since:
            out.append(row)
    return out


def version_context_for_archive(archive: Dict[str, Any]) -> Dict[str, Any]:
    snap = archive.get("snapshot_json") or {}
    game_ids = archive.get("game_ids") or []
    baseline_at = _parse_date(snap.get("generated_at") or archive.get("created_at"))
    retest_at = _parse_date(snap.get("last_retest_at") or snap.get("retested_at"))

    games: List[Dict[str, Any]] = []
    total_since_baseline = 0
    total_since_retest = 0

    for gid in game_ids:
        game = GameLibraryRepository.get(str(gid)) or {}
        all_versions = GameVersionRepository.list_for_game(str(gid), limit=30)
        since_baseline = _versions_since(all_versions, baseline_at)
        since_retest = _versions_since(all_versions, retest_at) if retest_at else since_baseline
        total_since_baseline += len(since_baseline)
        total_since_retest += len(since_retest)
        games.append(
            {
                "game_id": gid,
                "name": game.get("name") or gid,
                "version_count": len(all_versions),
                "since_baseline": since_baseline,
                "since_retest": since_retest,
            }
        )

    summary = ""
    if total_since_baseline:
        summary = f"自归档以来共 {total_since_baseline} 条版本/补丁记录"
        if retest_at and total_since_retest != total_since_baseline:
            summary += f"；上次复测后 {total_since_retest} 条"
    else:
        summary = "归档以来暂无版本记录（可在资料库导入 Steam 新闻或手动添加）"

    correlations: List[str] = []
    deltas = snap.get("last_retest_deltas") or snap.get("deltas") or []
    if deltas:
        for game_row in games:
            gname = game_row.get("name") or ""
            gid = str(game_row.get("game_id") or "")
            delta_row = next(
                (
                    d
                    for d in deltas
                    if d.get("product_name") == gname
                    or (gid and str(d.get("product_id") or "") in gid)
                    or (gid.endswith("_" + str(d.get("product_id") or "")))
                ),
                None,
            )
            if not delta_row:
                continue
            for ver in game_row.get("since_baseline") or []:
                label = ver.get("version_label") or "版本"
                released = ver.get("released_at") or ""
                sign = "+" if (delta_row.get("delta") or 0) >= 0 else ""
                correlations.append(
                    f"「{gname}」{released} {label} 后口碑 {sign}{delta_row.get('delta')}%"
                    f"（{delta_row.get('positive_rate_before')}%→{delta_row.get('positive_rate_after')}%）"
                )
                break

    return {
        "success": True,
        "baseline_at": (baseline_at.isoformat() if baseline_at else None),
        "last_retest_at": (retest_at.isoformat() if retest_at else None),
        "summary": summary,
        "games": games,
        "total_since_baseline": total_since_baseline,
        "correlations": correlations,
    }

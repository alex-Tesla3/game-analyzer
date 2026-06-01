"""Competitor workbench, archives, framework, and MVP timeline routes."""

from __future__ import annotations

import os
from typing import Optional

from fastapi import APIRouter, Body, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from src.services.analysis_archive import ARCHIVE_CATEGORIES, AnalysisArchiveRepository
from src.services.action_tasks import (
    apply_action_status_updates,
    export_actions_content,
    normalize_action_items,
)
from src.services.version_context import version_context_for_archive
from src.services.retest_loop import retest_from_archive
from src.services.competitor_scores import (
    COMPETITOR_DIMENSIONS,
    CompetitorScoreRepository,
    build_score_summary,
)
from src.services.competitor_workbench import (
    ANALYSIS_FRAMEWORK,
    build_compare_payload,
    build_feature_matrix,
    compare_snapshots,
    data_provenance_payload,
    list_mvp_snapshots,
    load_mvp_snapshot,
)
from src.services.scenario_ai import (
    archive_scenario_report,
    generate_breakdown_scenario_report,
    generate_competitor_scenario_report,
    generate_review_scenario_report,
    get_breakdowns_for_ids,
)
from src.services.game_intel import GameLibraryRepository
from src.web_common import get_current_user
from src.web_constants import BASE_DIR

router = APIRouter(tags=["competitor"])


def _read_template(name: str) -> str:
    path = os.path.join(BASE_DIR, "templates", name)
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


@router.get("/review")
async def review_redirect():
    return RedirectResponse(url="/games/review", status_code=307)


@router.get("/games/review", response_class=HTMLResponse)
async def review_page():
    return _read_template("review.html")


@router.get("/api/work/guidance")
async def api_work_guidance(token: Optional[str] = Query(None)):
    if not token:
        raise HTTPException(status_code=401, detail="Token required")
    user = await get_current_user(token)
    from src.services.work_guidance import work_guidance_summary

    return work_guidance_summary(user.username)


@router.get("/games/compare", response_class=HTMLResponse)
async def compare_page():
    return _read_template("compare.html")


@router.get("/framework", response_class=HTMLResponse)
async def framework_page():
    return _read_template("framework.html")


@router.get("/api/data/provenance")
async def get_data_provenance(token: Optional[str] = Query(None)):
    if not token:
        raise HTTPException(status_code=401, detail="Token required")
    user = await get_current_user(token)
    return data_provenance_payload(user.username)


@router.get("/api/games/compare")
async def api_compare(
    token: Optional[str] = Query(None),
    ids: Optional[str] = Query(None, description="Comma-separated game_id or product id"),
    genre: Optional[str] = Query(None),
):
    if not token:
        raise HTTPException(status_code=401, detail="Token required")
    user = await get_current_user(token)

    id_list = [x.strip() for x in (ids or "").split(",") if x.strip()]
    if not id_list and genre and genre != "all":
        games = GameLibraryRepository.list_games(username=user.username, genre=genre)
        id_list = [g["game_id"] for g in games[:5]]
    if not id_list:
        games = GameLibraryRepository.list_games(username=user.username)
        id_list = [g["game_id"] for g in games[:5]]
    if not id_list:
        raise HTTPException(status_code=400, detail="请选择至少一款游戏进行对比")

    payload = build_compare_payload(id_list, username=user.username)
    payload["feature_matrix"] = build_feature_matrix(id_list)
    payload["dimension_scores"] = CompetitorScoreRepository.get_batch(
        user.username,
        id_list,
        compare_items=payload.get("items") or [],
    )
    payload["score_summary"] = build_score_summary(payload["dimension_scores"].get("rows") or [])
    return payload


@router.get("/api/games/feature-matrix")
async def api_feature_matrix(
    token: Optional[str] = Query(None),
    ids: Optional[str] = Query(None),
):
    if not token:
        raise HTTPException(status_code=401, detail="Token required")
    await get_current_user(token)
    id_list = [x.strip() for x in (ids or "").split(",") if x.strip()]
    if not id_list:
        raise HTTPException(status_code=400, detail="ids required")
    return build_feature_matrix(id_list)


@router.get("/api/games/compare/scores")
async def get_compare_scores(
    token: Optional[str] = Query(None),
    ids: Optional[str] = Query(None),
):
    if not token:
        raise HTTPException(status_code=401, detail="Token required")
    user = await get_current_user(token)
    id_list = [x.strip() for x in (ids or "").split(",") if x.strip()]
    if not id_list:
        raise HTTPException(status_code=400, detail="ids required")
    compare = build_compare_payload(id_list, username=user.username)
    batch = CompetitorScoreRepository.get_batch(
        user.username,
        id_list,
        compare_items=compare.get("items") or [],
    )
    batch["summary"] = build_score_summary(batch.get("rows") or [])
    return batch


@router.put("/api/games/compare/scores")
async def save_compare_scores(
    token: Optional[str] = Query(None),
    body: dict = Body(default_factory=dict),
):
    if not token:
        raise HTTPException(status_code=401, detail="Token required")
    user = await get_current_user(token)
    game_id = body.get("game_id")
    scores = body.get("scores") or {}
    if not game_id:
        raise HTTPException(status_code=400, detail="game_id required")
    saved = CompetitorScoreRepository.upsert(user.username, str(game_id), scores)
    return {"success": True, "game_id": game_id, "scores": saved}


@router.get("/api/games/compare/dimensions")
async def compare_dimensions_meta(token: Optional[str] = Query(None)):
    if not token:
        raise HTTPException(status_code=401, detail="Token required")
    await get_current_user(token)
    return {"success": True, "dimensions": COMPETITOR_DIMENSIONS}


@router.get("/api/games/archives")
async def list_archives(
    token: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    tag: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
):
    if not token:
        raise HTTPException(status_code=401, detail="Token required")
    user = await get_current_user(token)
    items = AnalysisArchiveRepository.list_for_user(
        user.username,
        category=category,
        tag=tag,
        search=search,
    )
    return {
        "success": True,
        "archives": items,
        "total": len(items),
        "categories": ARCHIVE_CATEGORIES,
    }


@router.put("/api/games/archives/{archive_id}")
async def update_archive(
    archive_id: str,
    token: Optional[str] = Query(None),
    body: dict = Body(default_factory=dict),
):
    if not token:
        raise HTTPException(status_code=401, detail="Token required")
    user = await get_current_user(token)
    if not AnalysisArchiveRepository.get(archive_id, user.username):
        raise HTTPException(status_code=404, detail="归档不存在")
    AnalysisArchiveRepository.update(archive_id, user.username, body)
    return {"success": True, "archive": AnalysisArchiveRepository.get(archive_id, user.username)}


@router.get("/api/games/archives/{archive_id}")
async def get_archive(archive_id: str, token: Optional[str] = Query(None)):
    if not token:
        raise HTTPException(status_code=401, detail="Token required")
    user = await get_current_user(token)
    row = AnalysisArchiveRepository.get(archive_id, user.username)
    if not row:
        raise HTTPException(status_code=404, detail="归档不存在")
    return {"success": True, "archive": row}


@router.get("/api/mvp/snapshots")
async def mvp_snapshots(token: Optional[str] = Query(None)):
    if not token:
        raise HTTPException(status_code=401, detail="Token required")
    await get_current_user(token)
    return {"success": True, "snapshots": list_mvp_snapshots()}


@router.get("/api/mvp/snapshots/{snapshot_id}")
async def mvp_snapshot_detail(snapshot_id: str, token: Optional[str] = Query(None)):
    if not token:
        raise HTTPException(status_code=401, detail="Token required")
    await get_current_user(token)
    data = load_mvp_snapshot(snapshot_id)
    if not data:
        raise HTTPException(status_code=404, detail="快照不存在")
    return {"success": True, "snapshot": data}


@router.get("/api/mvp/snapshots/compare")
async def mvp_snapshot_compare(
    token: Optional[str] = Query(None),
    a: str = Query(...),
    b: str = Query(...),
):
    if not token:
        raise HTTPException(status_code=401, detail="Token required")
    await get_current_user(token)
    return compare_snapshots(a, b)


@router.get("/api/framework")
async def framework_json(token: Optional[str] = Query(None)):
    if not token:
        raise HTTPException(status_code=401, detail="Token required")
    await get_current_user(token)
    return {"success": True, "framework": ANALYSIS_FRAMEWORK}


@router.get("/api/scenarios/breakdowns")
async def inline_breakdowns(
    token: Optional[str] = Query(None),
    ids: Optional[str] = Query(None),
):
    if not token:
        raise HTTPException(status_code=401, detail="Token required")
    await get_current_user(token)
    id_list = [x.strip() for x in (ids or "").split(",") if x.strip()]
    if not id_list:
        raise HTTPException(status_code=400, detail="ids required")
    return get_breakdowns_for_ids(id_list)


@router.post("/api/scenarios/competitor/report")
async def competitor_ai_report(
    token: Optional[str] = Query(None),
    body: dict = Body(default_factory=dict),
):
    if not token:
        raise HTTPException(status_code=401, detail="Token required")
    user = await get_current_user(token)
    ids = body.get("ids") or []
    if isinstance(ids, str):
        ids = [x.strip() for x in ids.split(",") if x.strip()]
    return await generate_competitor_scenario_report(ids, username=user.username)


@router.post("/api/scenarios/breakdown/report")
async def breakdown_ai_report(
    token: Optional[str] = Query(None),
    body: dict = Body(default_factory=dict),
):
    if not token:
        raise HTTPException(status_code=401, detail="Token required")
    user = await get_current_user(token)
    game_ids = body.get("game_ids") or body.get("ids") or []
    if body.get("game_id"):
        game_ids = [body["game_id"]]
    if isinstance(game_ids, str):
        game_ids = [x.strip() for x in game_ids.split(",") if x.strip()]
    return await generate_breakdown_scenario_report(game_ids, username=user.username)


@router.post("/api/scenarios/review/report")
async def review_ai_report(
    token: Optional[str] = Query(None),
    body: dict = Body(default_factory=dict),
):
    if not token:
        raise HTTPException(status_code=401, detail="Token required")
    user = await get_current_user(token)
    product_ids = body.get("product_ids")
    if isinstance(product_ids, str):
        product_ids = [x.strip() for x in product_ids.split(",") if x.strip()]
    return await generate_review_scenario_report(
        username=user.username,
        snapshot_a=body.get("snapshot_a"),
        snapshot_b=body.get("snapshot_b"),
        product_ids=product_ids,
    )


@router.post("/api/scenarios/archive")
async def archive_scenario(
    token: Optional[str] = Query(None),
    body: dict = Body(default_factory=dict),
):
    if not token:
        raise HTTPException(status_code=401, detail="Token required")
    user = await get_current_user(token)
    report = body.get("report")
    if not report or not report.get("success"):
        raise HTTPException(status_code=400, detail="无效报告")
    archive_id = archive_scenario_report(user.username, report)
    return {"success": True, "archive_id": archive_id}


@router.post("/api/games/archives/{archive_id}/share")
async def share_archive(
    archive_id: str,
    request: Request,
    token: Optional[str] = Query(None),
    body: dict = Body(default_factory=dict),
):
    if not token:
        raise HTTPException(status_code=401, detail="Token required")
    user = await get_current_user(token)
    from src.services.archive_share import create_archive_share_link

    expires = int(body.get("expires_hours") or 168)
    base = str(request.base_url).rstrip("/")
    return create_archive_share_link(
        user.username,
        archive_id,
        expires_hours=expires,
        base_url=base,
    )


@router.get("/api/games/archives/{archive_id}/versions")
async def archive_version_context(archive_id: str, token: Optional[str] = Query(None)):
    if not token:
        raise HTTPException(status_code=401, detail="Token required")
    user = await get_current_user(token)
    archive = AnalysisArchiveRepository.get(archive_id, user.username)
    if not archive:
        raise HTTPException(status_code=404, detail="归档不存在")
    return version_context_for_archive(archive)


@router.post("/api/games/archives/{archive_id}/retest")
async def retest_archive(
    archive_id: str,
    token: Optional[str] = Query(None),
    body: dict = Body(default_factory=dict),
):
    if not token:
        raise HTTPException(status_code=401, detail="Token required")
    user = await get_current_user(token)
    result = await retest_from_archive(
        archive_id,
        username=user.username,
        max_reviews=int(body.get("max_reviews") or 50),
        auto_archive=body.get("auto_archive", True) is not False,
    )
    return result


@router.patch("/api/games/archives/{archive_id}/actions")
async def patch_archive_actions(
    archive_id: str,
    token: Optional[str] = Query(None),
    body: dict = Body(default_factory=dict),
):
    if not token:
        raise HTTPException(status_code=401, detail="Token required")
    user = await get_current_user(token)
    archive = AnalysisArchiveRepository.get(archive_id, user.username)
    if not archive:
        raise HTTPException(status_code=404, detail="归档不存在")
    snap = archive.get("snapshot_json") or {}
    current = normalize_action_items(snap.get("action_items") or [])
    updates = body.get("updates") or body.get("items") or {}
    if isinstance(updates, list):
        merged = normalize_action_items(updates)
    else:
        merged = apply_action_status_updates(current, updates)
    AnalysisArchiveRepository.update_action_items(archive_id, user.username, merged)
    return {"success": True, "action_items": merged}


@router.get("/api/games/archives/{archive_id}/actions/export")
async def export_archive_actions(
    archive_id: str,
    token: Optional[str] = Query(None),
    fmt: str = Query("csv", alias="format"),
):
    if not token:
        raise HTTPException(status_code=401, detail="Token required")
    user = await get_current_user(token)
    archive = AnalysisArchiveRepository.get(archive_id, user.username)
    if not archive:
        raise HTTPException(status_code=404, detail="归档不存在")
    items = normalize_action_items((archive.get("snapshot_json") or {}).get("action_items") or [])
    title = (archive.get("title") or "actions").replace("/", "-")[:40]
    content, media_type, ext = export_actions_content(items, fmt, title=title)
    from fastapi.responses import PlainTextResponse

    return PlainTextResponse(
        content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="actions-{archive_id[:8]}.{ext}"'},
    )

"""Industry hotspot article API and page."""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, HTTPException, Query, Request
from fastapi.responses import HTMLResponse

from src.services.analysis_archive import AnalysisArchiveRepository
from src.services.hotspot_articles import (
    build_article_fact_pack,
    discover_hotspot_topics,
    generate_hotspot_article,
)
from src.web_common import get_current_user
from src.web_constants import BASE_DIR

router = APIRouter(tags=["hotspot"])


def _read_template(name: str) -> str:
    path = os.path.join(BASE_DIR, "templates", name)
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


@router.get("/hotspot", response_class=HTMLResponse)
async def hotspot_page():
    return _read_template("hotspot.html")


@router.get("/api/hotspot/topics")
async def list_hotspot_topics(
    request: Request,
    token: Optional[str] = Query(None),
    limit: int = Query(12, ge=1, le=30),
):
    user = await get_current_user(request, token)
    topics = discover_hotspot_topics(user.username, limit=limit)
    return {
        "success": True,
        "topics": topics,
        "data_basis": topics[0]["data_basis"] if topics else "empty",
    }


@router.get("/api/hotspot/facts")
async def hotspot_facts(
    request: Request,
    token: Optional[str] = Query(None),
    product_id: str = Query(...),
    angle: str = Query("revenue_decline"),
):
    user = await get_current_user(request, token)
    facts = build_article_fact_pack(user.username, product_id, angle=angle)
    return {"success": True, "facts": facts}


@router.post("/api/hotspot/generate")
async def hotspot_generate(
    request: Request,
    token: Optional[str] = Query(None),
    body: Dict[str, Any] = Body(default_factory=dict),
):
    user = await get_current_user(request, token)
    product_id = str(body.get("product_id") or "").strip()
    if not product_id:
        raise HTTPException(status_code=400, detail="product_id 必填")
    result = await generate_hotspot_article(
        user.username,
        product_id=product_id,
        angle=str(body.get("angle") or "revenue_decline"),
        custom_title=(body.get("title") or "").strip() or None,
    )
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message") or "生成失败")
    return result


@router.post("/api/hotspot/archive")
async def hotspot_archive(
    request: Request,
    token: Optional[str] = Query(None),
    body: Dict[str, Any] = Body(default_factory=dict),
):
    user = await get_current_user(request, token)
    title = str(body.get("title") or "").strip()
    markdown = str(body.get("markdown") or "").strip()
    if not title or not markdown:
        raise HTTPException(status_code=400, detail="title 与 markdown 必填")

    archive_id = AnalysisArchiveRepository.create(
        username=user.username,
        title=title,
        report_type="hotspot",
        category="行业热点",
        product_ids=[str(body.get("product_id"))] if body.get("product_id") else [],
        body_markdown=markdown,
        html_excerpt=(body.get("html") or "")[:4000],
        snapshot={"angle": body.get("angle"), "facts": body.get("facts")},
    )
    return {"success": True, "archive_id": archive_id}

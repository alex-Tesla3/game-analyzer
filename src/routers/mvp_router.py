"""MVP Steam crawl and dashboard routes."""

from __future__ import annotations

import asyncio
import os
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse

from src.mvp_data import load_mvp_artifact
from src.mvp_pipeline import DEFAULT_STEAM_APP_IDS, run_mvp_pipeline

router = APIRouter(tags=["mvp"])

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@router.get("/mvp", response_class=HTMLResponse)
async def mvp_page():
    template_path = os.path.join(BASE_DIR, "templates", "mvp.html")
    if os.path.exists(template_path):
        with open(template_path, "r", encoding="utf-8") as handle:
            return handle.read()
    raise HTTPException(status_code=404, detail="MVP dashboard template not found")


@router.get("/api/mvp/latest")
async def get_latest_mvp():
    dataset = load_mvp_artifact("dataset")
    analysis = load_mvp_artifact("analysis")
    validation = load_mvp_artifact("validation")
    if not dataset or not analysis or not validation:
        raise HTTPException(
            status_code=404,
            detail="MVP artifact not found. Run /api/mvp/steam first.",
        )
    return {
        "success": True,
        "dataset": dataset,
        "analysis": analysis,
        "validation": validation,
    }


@router.get("/api/mvp/steam")
async def run_steam_mvp(
    app_ids: str = Query(",".join(DEFAULT_STEAM_APP_IDS)),
    max_reviews: int = Query(25, ge=1, le=100),
):
    selected_app_ids = [item.strip() for item in app_ids.split(",") if item.strip()]
    if not selected_app_ids:
        raise HTTPException(status_code=400, detail="至少需要提供一个 Steam app_id")
    try:
        result = await asyncio.to_thread(
            run_mvp_pipeline,
            app_ids=selected_app_ids,
            max_reviews_per_app=max_reviews,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Steam MVP pipeline failed: {exc}") from exc
    return {
        "success": result["success"],
        "summary": result["analysis"]["summary"],
        "product_reports": result["analysis"]["product_reports"],
        "ai_strategy": result["analysis"].get("ai_strategy"),
        "validation": result["validation"],
        "artifacts": result["artifacts"],
        "crawl_errors": result["dataset"].get("errors", []),
    }

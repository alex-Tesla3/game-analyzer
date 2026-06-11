"""MVP Steam crawl and dashboard routes."""

from __future__ import annotations

import asyncio
import os
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse

from src.mvp_data import load_mvp_artifact
from src.mvp_pipeline import DEFAULT_STEAM_APP_IDS, run_mvp_pipeline, steam_app_catalog
from src.product_registry import get_mvp_presets, resolve_mvp_crawl_targets
from src.services.google_play_pipeline import run_google_play_pipeline
from src.services.taptap_pipeline import run_taptap_pipeline

router = APIRouter(tags=["mvp"])

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@router.get("/mvp", response_class=HTMLResponse)
async def mvp_page():
    template_path = os.path.join(BASE_DIR, "templates", "mvp.html")
    if os.path.exists(template_path):
        with open(template_path, "r", encoding="utf-8") as handle:
            return handle.read()
    raise HTTPException(status_code=404, detail="MVP dashboard template not found")


@router.get("/api/mvp/catalog")
async def get_mvp_catalog():
    """Product + channel options for the MVP page filters."""
    products = steam_app_catalog()
    seen = {p["id"] for p in products}
    dataset = load_mvp_artifact("dataset")
    if dataset:
        for game in dataset.get("games") or []:
            app_id = str(game.get("app_id") or "").strip()
            if not app_id or app_id in seen:
                continue
            genres = game.get("genres") or []
            products.append(
                {
                    "id": app_id,
                    "name": game.get("name") or f"Steam App {app_id}",
                    "genre": genres[0] if genres else "",
                }
            )
            seen.add(app_id)
    if dataset:
        for game in dataset.get("games") or []:
            platform = str(game.get("platform") or "").lower()
            gid = str(game.get("app_id") or game.get("package_id") or "").strip()
            name = game.get("name") or gid
            if platform == "taptap" and gid and gid not in seen:
                products.append({"id": gid, "name": name, "genre": "", "platform": "taptap"})
                seen.add(gid)
            elif platform == "google play" and gid and gid not in seen:
                products.append({"id": gid, "name": name, "genre": "", "platform": "google_play"})
                seen.add(gid)
    preset_platform = get_mvp_presets()
    for item in preset_platform:
        if item["id"] not in seen:
            products.append(item)
            seen.add(item["id"])
    channels = [
        {"id": "steam", "label": "Steam", "crawl_supported": True},
        {"id": "taptap", "label": "TapTap", "crawl_supported": True},
        {"id": "google_play", "label": "Google Play", "crawl_supported": True},
        {"id": "app_store", "label": "App Store", "crawl_supported": False},
    ]
    return {
        "success": True,
        "products": products,
        "channels": channels,
        "default_product_ids": list(DEFAULT_STEAM_APP_IDS),
        "default_by_channel": {
            "steam": list(DEFAULT_STEAM_APP_IDS),
            "taptap": ["168332"],
            "google_play": ["com.miHoYo.GenshinImpact"],
        },
    }


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


@router.get("/api/mvp/resolve")
async def resolve_mvp_inputs(
    platform: str = Query("steam"),
    q: str = Query("", description="Game names, package names, or app ids"),
):
    app_ids, overrides, errors = resolve_mvp_crawl_targets(platform, q, "")
    return {
        "success": bool(app_ids),
        "platform": platform,
        "app_ids": app_ids,
        "display_names": overrides,
        "errors": errors,
    }


@router.get("/api/mvp/steam")
async def run_steam_mvp(
    app_ids: str = Query(",".join(DEFAULT_STEAM_APP_IDS)),
    max_reviews: int = Query(25, ge=1, le=100),
    product_names: str = Query("", description="Custom display names: product_id:名称"),
):
    selected_app_ids, name_overrides, resolve_errors = resolve_mvp_crawl_targets(
        "steam", app_ids, product_names
    )
    if not selected_app_ids:
        detail = "；".join(resolve_errors) if resolve_errors else "至少需要提供一个 Steam app_id"
        raise HTTPException(status_code=400, detail=detail)
    try:
        result = await asyncio.to_thread(
            run_mvp_pipeline,
            app_ids=selected_app_ids,
            max_reviews_per_app=max_reviews,
            product_name_overrides=name_overrides or None,
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
        "data_mode": result["dataset"].get("data_mode", "live"),
        "crawled_app_ids": selected_app_ids,
        "display_names": name_overrides,
    }


@router.get("/api/mvp/taptap")
async def run_taptap_mvp(
    app_ids: str = Query("", description="Comma-separated TapTap app ids or game names"),
    max_reviews: int = Query(25, ge=1, le=100),
    product_names: str = Query("", description="Custom display names: app_id:名称"),
):
    selected, name_overrides, resolve_errors = resolve_mvp_crawl_targets(
        "taptap", app_ids, product_names
    )
    if not selected:
        detail = "；".join(resolve_errors) if resolve_errors else "至少需要提供一个 TapTap AppID"
        raise HTTPException(status_code=400, detail=detail)
    try:
        result = await asyncio.to_thread(
            run_taptap_pipeline,
            app_ids=selected,
            max_reviews_per_app=max_reviews,
            product_name_overrides=name_overrides or None,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"TapTap pipeline failed: {exc}") from exc
    analysis = load_mvp_artifact("analysis") or {}
    return {
        "success": result["success"],
        "platform": "taptap",
        "data_mode": result.get("data_mode"),
        "summary": (analysis.get("summary") if analysis else None),
        "validation": result.get("validation"),
        "artifacts": result.get("artifacts"),
        "crawl_errors": (result.get("dataset") or {}).get("errors", []),
        "crawled_app_ids": selected,
        "display_names": name_overrides,
    }


@router.get("/api/mvp/google-play")
async def run_google_play_mvp(
    app_ids: str = Query("", description="Comma-separated package names or game names"),
    max_reviews: int = Query(25, ge=1, le=100),
    product_names: str = Query("", description="Custom display names: package:名称"),
):
    selected, name_overrides, resolve_errors = resolve_mvp_crawl_targets(
        "google_play", app_ids, product_names
    )
    if not selected:
        detail = "；".join(resolve_errors) if resolve_errors else "至少需要提供一个 Google Play 包名"
        raise HTTPException(status_code=400, detail=detail)
    try:
        result = await asyncio.to_thread(
            run_google_play_pipeline,
            app_ids=selected,
            max_reviews_per_app=max_reviews,
            product_name_overrides=name_overrides or None,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Google Play pipeline failed: {exc}") from exc
    analysis = load_mvp_artifact("analysis") or {}
    return {
        "success": result["success"],
        "platform": "google_play",
        "data_mode": result.get("data_mode"),
        "summary": (analysis.get("summary") if analysis else None),
        "validation": result.get("validation"),
        "artifacts": result.get("artifacts"),
        "crawl_errors": (result.get("dataset") or {}).get("errors", []),
        "crawled_app_ids": selected,
        "display_names": name_overrides,
    }

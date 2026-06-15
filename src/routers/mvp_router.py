"""MVP Steam crawl and dashboard routes."""

from __future__ import annotations

import asyncio
import os
from typing import Optional

from fastapi import APIRouter, Body, HTTPException, Query
from fastapi.responses import HTMLResponse

from src.mvp_data import load_mvp_artifact
from src.mvp_pipeline import DEFAULT_STEAM_APP_IDS, run_mvp_pipeline, steam_app_catalog
from src.product_registry import (
    add_custom_product,
    get_mvp_presets,
    load_custom_products,
    resolve_mvp_crawl_targets,
)
from src.services.google_play_pipeline import run_google_play_pipeline
from src.services.market_locale import (
    default_market_for_channel,
    get_market_profile,
    list_markets_for_channel,
    normalize_market_country,
)
from src.services.mvp_storage import resolve_mvp_output_dir
from src.services.review_window import (
    DEFAULT_REVIEW_DAYS,
    crawl_filter_description,
    normalize_max_reviews,
    normalize_review_days,
)
from src.services.taptap_pipeline import run_taptap_pipeline
from src.web_common import get_current_user


def _resolve_crawl_filters(
    *,
    use_review_days: bool,
    review_days: int,
    use_max_reviews: bool,
    max_reviews: int,
) -> dict:
    if not use_review_days and not use_max_reviews:
        raise HTTPException(
            status_code=400,
            detail="至少勾选「时间范围」或「评价数量」之一",
        )
    window_days = normalize_review_days(review_days) if use_review_days else None
    review_cap = normalize_max_reviews(max_reviews) if use_max_reviews else None
    if use_max_reviews and review_cap is None:
        raise HTTPException(status_code=400, detail="启用评价数量时请填写大于 0 的条数")
    return {
        "use_review_days": use_review_days,
        "review_days": window_days,
        "use_max_reviews": use_max_reviews,
        "max_reviews_per_app": review_cap,
        "filter_label": crawl_filter_description(
            use_review_days=use_review_days,
            review_days=window_days,
            use_max_reviews=use_max_reviews,
            max_reviews=review_cap,
        ),
    }


def _resolve_market(channel: str, market_country: str) -> dict:
    normalized = normalize_market_country(channel, market_country)
    profile = get_market_profile(channel, normalized)
    return {
        "market_country": profile.country,
        "market_label": profile.label,
    }


router = APIRouter(tags=["mvp"])

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


async def _mvp_scope(token: Optional[str]) -> tuple[Optional[str], str]:
    if not token:
        return None, resolve_mvp_output_dir(None)
    user = await get_current_user(token)
    return user.username, resolve_mvp_output_dir(user.username)


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
        {"id": "app_store", "label": "App Store（即将支持）", "crawl_supported": False},
    ]
    markets_by_channel = {
        channel["id"]: list_markets_for_channel(channel["id"])
        for channel in channels
        if channel.get("crawl_supported")
    }
    default_market_by_channel = {
        channel["id"]: default_market_for_channel(channel["id"])
        for channel in channels
        if channel.get("crawl_supported")
    }
    return {
        "success": True,
        "products": products,
        "channels": channels,
        "markets_by_channel": markets_by_channel,
        "default_market_by_channel": default_market_by_channel,
        "default_product_ids": list(DEFAULT_STEAM_APP_IDS),
        "default_by_channel": {
            "steam": list(DEFAULT_STEAM_APP_IDS),
            "taptap": ["168332"],
            "google_play": [
                "com.fun.lastwar.gp",
                "com.readygo.dark.gp",
                "com.hnhs.endlesssea.gp",
            ],
        },
    }


@router.get("/api/mvp/latest")
async def get_latest_mvp(
    channel: str = Query("", description="Optional: steam | taptap | google_play"),
    token: Optional[str] = Query(None, description="User token for per-tenant MVP data"),
):
    _, output_dir = await _mvp_scope(token)
    dataset = load_mvp_artifact("dataset", output_dir)
    analysis = load_mvp_artifact("analysis", output_dir)
    validation = load_mvp_artifact("validation", output_dir)
    if not dataset or not analysis or not validation:
        raise HTTPException(
            status_code=404,
            detail="MVP artifact not found. Run /api/mvp/steam first.",
        )
    channel_key = (channel or "").strip().lower()
    platform_artifacts = {
        "google_play": "google_play_dataset",
        "taptap": "taptap_dataset",
    }
    if channel_key in platform_artifacts:
        platform_blob = load_mvp_artifact(platform_artifacts[channel_key], output_dir)
        if platform_blob:
            if platform_blob.get("analysis"):
                analysis = platform_blob["analysis"]
            if platform_blob.get("validation"):
                validation = platform_blob["validation"]
            dataset = platform_blob
    return {
        "success": True,
        "dataset": dataset,
        "analysis": analysis,
        "validation": validation,
    }


@router.get("/api/mvp/custom-products")
async def list_custom_products():
    products = []
    for entry in load_custom_products():
        name = str(entry.get("display_name") or "")
        genre = str(entry.get("genre") or "")
        for plat, pid in (entry.get("platforms") or {}).items():
            products.append(
                {
                    "id": str(pid),
                    "name": name,
                    "genre": genre,
                    "platform": plat,
                    "user_added": True,
                }
            )
    return {"success": True, "products": products}


@router.post("/api/mvp/custom-products")
async def create_custom_product(body: dict = Body(default_factory=dict)):
    try:
        result = add_custom_product(
            display_name=str(body.get("name") or body.get("display_name") or ""),
            platform=str(body.get("platform") or "google_play"),
            product_id=str(body.get("product_id") or body.get("id") or ""),
            genre=str(body.get("genre") or ""),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result


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
    use_review_days: bool = Query(True, description="按评论发布日期筛选"),
    review_days: int = Query(
        DEFAULT_REVIEW_DAYS, ge=7, le=30, description="近 N 天评论（7/14/30，按发布日期）"
    ),
    use_max_reviews: bool = Query(False, description="限制每产品抓取条数"),
    max_reviews: int = Query(0, ge=0, description="每产品最多抓取条数（无上限，由用户填写）"),
    market_country: str = Query("", description="渠道所在国家/地区（如 us、cn、jp）"),
    product_names: str = Query("", description="Custom display names: product_id:名称"),
    token: Optional[str] = Query(None, description="User token (required for isolated crawl data)"),
):
    username, output_dir = await _mvp_scope(token)
    selected_app_ids, name_overrides, resolve_errors = resolve_mvp_crawl_targets(
        "steam", app_ids, product_names
    )
    if not selected_app_ids:
        detail = "；".join(resolve_errors) if resolve_errors else "至少需要提供一个 Steam app_id"
        raise HTTPException(status_code=400, detail=detail)
    filters = _resolve_crawl_filters(
        use_review_days=use_review_days,
        review_days=review_days,
        use_max_reviews=use_max_reviews,
        max_reviews=max_reviews,
    )
    market = _resolve_market("steam", market_country)
    try:
        result = await asyncio.to_thread(
            run_mvp_pipeline,
            app_ids=selected_app_ids,
            output_dir=output_dir,
            product_name_overrides=name_overrides or None,
            review_days=filters["review_days"],
            use_review_days=filters["use_review_days"],
            use_max_reviews=filters["use_max_reviews"],
            max_reviews_per_app=filters["max_reviews_per_app"],
            market_country=market["market_country"],
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Steam MVP pipeline failed: {exc}") from exc
    return {
        "success": result["success"],
        "username": username,
        "output_dir": output_dir,
        "use_review_days": filters["use_review_days"],
        "review_days": filters["review_days"],
        "use_max_reviews": filters["use_max_reviews"],
        "max_reviews_per_app": filters["max_reviews_per_app"],
        "filter_label": filters["filter_label"],
        "market_country": market["market_country"],
        "market_label": market["market_label"],
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
    use_review_days: bool = Query(True, description="按评论发布日期筛选"),
    review_days: int = Query(
        DEFAULT_REVIEW_DAYS, ge=7, le=30, description="近 N 天评论（7/14/30）"
    ),
    use_max_reviews: bool = Query(False, description="限制每产品抓取条数"),
    max_reviews: int = Query(0, ge=0, description="每产品最多抓取条数（无上限，由用户填写）"),
    market_country: str = Query("", description="渠道所在国家/地区（如 cn、us、jp）"),
    product_names: str = Query("", description="Custom display names: app_id:名称"),
    token: Optional[str] = Query(None, description="User token for per-tenant crawl data"),
):
    username, output_dir = await _mvp_scope(token)
    selected, name_overrides, resolve_errors = resolve_mvp_crawl_targets(
        "taptap", app_ids, product_names
    )
    if not selected:
        detail = "；".join(resolve_errors) if resolve_errors else "至少需要提供一个 TapTap AppID"
        raise HTTPException(status_code=400, detail=detail)
    filters = _resolve_crawl_filters(
        use_review_days=use_review_days,
        review_days=review_days,
        use_max_reviews=use_max_reviews,
        max_reviews=max_reviews,
    )
    market = _resolve_market("taptap", market_country)
    try:
        result = await asyncio.to_thread(
            run_taptap_pipeline,
            app_ids=selected,
            output_dir=output_dir,
            product_name_overrides=name_overrides or None,
            review_days=filters["review_days"],
            use_review_days=filters["use_review_days"],
            use_max_reviews=filters["use_max_reviews"],
            max_reviews_per_app=filters["max_reviews_per_app"],
            market_country=market["market_country"],
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"TapTap pipeline failed: {exc}") from exc
    analysis = load_mvp_artifact("analysis", output_dir) or {}
    return {
        "success": result["success"],
        "username": username,
        "output_dir": output_dir,
        "use_review_days": filters["use_review_days"],
        "review_days": filters["review_days"],
        "use_max_reviews": filters["use_max_reviews"],
        "max_reviews_per_app": filters["max_reviews_per_app"],
        "filter_label": filters["filter_label"],
        "market_country": market["market_country"],
        "market_label": market["market_label"],
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
    use_review_days: bool = Query(True, description="按评论发布日期筛选"),
    review_days: int = Query(
        DEFAULT_REVIEW_DAYS, ge=7, le=30, description="近 N 天评论（7/14/30）"
    ),
    use_max_reviews: bool = Query(False, description="限制每产品抓取条数"),
    max_reviews: int = Query(0, ge=0, description="每产品最多抓取条数（无上限，由用户填写）"),
    market_country: str = Query("", description="渠道所在国家/地区（如 us、cn、jp）"),
    product_names: str = Query("", description="Custom display names: package:名称"),
    token: Optional[str] = Query(None, description="User token for per-tenant crawl data"),
):
    username, output_dir = await _mvp_scope(token)
    selected, name_overrides, resolve_errors = resolve_mvp_crawl_targets(
        "google_play", app_ids, product_names
    )
    if not selected:
        detail = "；".join(resolve_errors) if resolve_errors else "至少需要提供一个 Google Play 包名"
        raise HTTPException(status_code=400, detail=detail)
    filters = _resolve_crawl_filters(
        use_review_days=use_review_days,
        review_days=review_days,
        use_max_reviews=use_max_reviews,
        max_reviews=max_reviews,
    )
    market = _resolve_market("google_play", market_country)
    try:
        result = await asyncio.to_thread(
            run_google_play_pipeline,
            app_ids=selected,
            output_dir=output_dir,
            product_name_overrides=name_overrides or None,
            review_days=filters["review_days"],
            use_review_days=filters["use_review_days"],
            use_max_reviews=filters["use_max_reviews"],
            max_reviews_per_app=filters["max_reviews_per_app"],
            market_country=market["market_country"],
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Google Play pipeline failed: {exc}") from exc
    analysis = load_mvp_artifact("analysis", output_dir) or {}
    return {
        "success": result["success"],
        "username": username,
        "output_dir": output_dir,
        "use_review_days": filters["use_review_days"],
        "review_days": filters["review_days"],
        "use_max_reviews": filters["use_max_reviews"],
        "max_reviews_per_app": filters["max_reviews_per_app"],
        "filter_label": filters["filter_label"],
        "market_country": market["market_country"],
        "market_label": market["market_label"],
        "platform": "google_play",
        "data_mode": result.get("data_mode"),
        "summary": (analysis.get("summary") if analysis else None),
        "validation": result.get("validation"),
        "artifacts": result.get("artifacts"),
        "crawl_errors": (result.get("dataset") or {}).get("errors", []),
        "crawled_app_ids": selected,
        "display_names": name_overrides,
        "review_counts": (result.get("dataset") or {}).get("review_counts"),
        "review_locale": (result.get("dataset") or {}).get("review_locale"),
    }

"""Commercial deployment status and customer-facing trust pages."""

from __future__ import annotations

import os

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from src.commercial_config import commercial_status_payload
from src.web_constants import BASE_DIR

router = APIRouter(tags=["commercial"])

_TRUST_HTML = os.path.join(BASE_DIR, "templates", "data_trust.html")


@router.get("/api/commercial/status")
async def get_commercial_status():
    """Public deployment / payment mode for UI banners (no auth)."""
    return {"success": True, **commercial_status_payload()}


@router.get("/trust", response_class=HTMLResponse)
async def data_trust_page():
    with open(_TRUST_HTML, "r", encoding="utf-8") as handle:
        return handle.read()

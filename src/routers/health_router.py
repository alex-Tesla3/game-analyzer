"""Health check endpoint for deploy probes."""

from __future__ import annotations

import os
from datetime import datetime

from fastapi import APIRouter

from database import config_manager
from src.db_dialect import resolve_database_backend

router = APIRouter(tags=["health"])

APP_VERSION = os.getenv("APP_VERSION", "1.0.0")


@router.get("/api/health")
async def health_check():
    app_env = os.getenv("APP_ENV", "development").lower()
    allow_demo = os.getenv("ALLOW_DEMO_ACCOUNTS", "true").strip().lower() in ("1", "true", "yes")
    db_type, _ = resolve_database_backend(config_manager)
    return {
        "status": "ok",
        "service": "game_analyzer",
        "version": APP_VERSION,
        "environment": app_env,
        "database_type": db_type,
        "demo_accounts_enabled": allow_demo and app_env != "production",
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }

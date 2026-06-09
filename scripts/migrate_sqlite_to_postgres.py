#!/usr/bin/env python3
"""
Copy data from SQLite (data/game_analyzer.db) into PostgreSQL (DATABASE_URL).

Usage:
  export DATABASE_URL=postgresql://game:game@localhost:5432/game_analyzer
  PYTHONPATH=src python scripts/migrate_sqlite_to_postgres.py
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

TABLES_ORDER = [
    "users",
    "llm_config",
    "operation_logs",
    "dashboard_configs",
    "alert_rules",
    "teams",
    "team_members",
    "dashboard_shares",
    "shared_reports",
    "orders",
    "products",
    "data_source_configs",
    "imported_metrics",
    "imported_comments",
    "cached_metrics",
    "cached_comments",
    "consent_logs",
    "reminder_logs",
    "health_logs",
    "error_logs",
    "user_events",
    "support_tickets",
    "ticket_replies",
    "live_chats",
    "chat_messages",
    "registration_events",
    "login_events",
    "device_accounts",
    "device_trial_claims",
    "game_library",
    "gameplay_breakdowns",
    "analysis_archives",
    "game_version_history",
    "competitor_dimension_scores",
]

PG_QUOTED_COLS = {"值", "内容", "日期", "用户角色", "情绪"}


def sqlite_path() -> Path:
    p = os.getenv("SQLITE_PATH", "data/game_analyzer.db")
    path = Path(p)
    if not path.is_absolute():
        path = ROOT / path
    return path


def quote_col(name: str) -> str:
    return f'"{name}"' if name in PG_QUOTED_COLS else name


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate SQLite → PostgreSQL")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    db_url = os.getenv("DATABASE_URL", "").strip()
    if not db_url:
        print("ERROR: set DATABASE_URL=postgresql://...", file=sys.stderr)
        return 1

    sp = sqlite_path()
    if not sp.is_file():
        print(f"ERROR: SQLite file not found: {sp}", file=sys.stderr)
        return 1

    if args.dry_run:
        print("Would migrate tables:", ", ".join(TABLES_ORDER))
        print(f"  from {sp}")
        print(f"  to   {db_url.split('@')[-1] if '@' in db_url else db_url}")
        return 0

    sys.path.insert(0, str(SRC))
    os.environ["DATABASE_URL"] = db_url

    import importlib

    import database as db_mod

    importlib.reload(db_mod)
    db_mod.init_database()

    import psycopg2
    from psycopg2.extras import execute_batch

    src = sqlite3.connect(str(sp))
    src.row_factory = sqlite3.Row
    dst = psycopg2.connect(db_url)
    dst.autocommit = False

    try:
        for table in TABLES_ORDER:
            try:
                rows = src.execute(f"SELECT * FROM {table}").fetchall()
            except sqlite3.OperationalError:
                print(f"  skip {table} (not in sqlite)")
                continue
            if not rows:
                print(f"  {table}: 0 rows")
                continue
            cols = list(rows[0].keys())
            col_list = ", ".join(quote_col(c) for c in cols)
            placeholders = ", ".join(["%s"] * len(cols))
            sql = f"INSERT INTO {table} ({col_list}) VALUES ({placeholders}) ON CONFLICT DO NOTHING"
            data = [tuple(r[c] for c in cols) for r in rows]
            with dst.cursor() as cur:
                execute_batch(cur, sql, data, page_size=200)
            print(f"  {table}: {len(rows)} rows")
        dst.commit()
        print("Migration complete.")
    except Exception as exc:
        dst.rollback()
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    finally:
        src.close()
        dst.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

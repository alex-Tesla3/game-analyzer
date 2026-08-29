"""Supabase (Postgres + pgvector) storage for crawled game data.

This module is a self-contained data layer for the AI pipeline (reviews,
LLM labels, embeddings, noise flags, metrics). It uses its own connection
string (``SUPABASE_DATABASE_URL``) so the app's operational database
(auth/orders, currently SQLite) is untouched.

Schema lives in the ``public`` schema. RLS is enabled on all tables and no
policies are created, so the Supabase Data API cannot read them with the
``anon`` role; only privileged connections (postgres owner / service role)
can access — which is exactly how this backend connects.

Env vars:
* ``SUPABASE_DATABASE_URL``  - Postgres connection string (required to enable)
* ``SUPABASE_SSLMODE``       - default ``require``
* ``EMBEDDING_DIM``          - vector dimension (default 1536, OpenAI)
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

import psycopg2
import psycopg2.extras

_ENV_URL = "SUPABASE_DATABASE_URL"
_DEFAULT_DIM = 1536

_IDENT_RE = re.compile(r"^[a-z_][a-z0-9_]*$")


def database_url() -> str:
    return os.getenv(_ENV_URL, "").strip()


def enabled() -> bool:
    return bool(database_url())


def embedding_dim() -> int:
    try:
        return int(os.getenv("EMBEDDING_DIM", str(_DEFAULT_DIM)).strip())
    except ValueError:
        return _DEFAULT_DIM


def sslmode() -> str:
    return os.getenv("SUPABASE_SSLMODE", "require").strip() or "require"


def connect():
    """Open a psycopg2 connection to Supabase."""
    if not enabled():
        raise RuntimeError("SUPABASE_DATABASE_URL not configured")
    return psycopg2.connect(database_url(), sslmode=sslmode(), connect_timeout=20)


def _validate_identifier(name: str) -> str:
    if not _IDENT_RE.match(name):
        raise ValueError(f"invalid identifier: {name}")
    return name


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

def schema_sql(dim: Optional[int] = None) -> str:
    dim = dim or embedding_dim()
    return f"""
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS games (
    game_id      TEXT PRIMARY KEY,
    platform     TEXT NOT NULL DEFAULT 'steam',
    name         TEXT NOT NULL,
    genre        TEXT,
    metadata     JSONB NOT NULL DEFAULT '{{}}'::jsonb,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS reviews (
    review_id     TEXT PRIMARY KEY,
    game_id       TEXT NOT NULL,
    platform      TEXT NOT NULL DEFAULT 'steam',
    username      TEXT,               -- 数据归属(可选)
    author        TEXT,
    title         TEXT,
    content       TEXT NOT NULL,
    lang          TEXT,
    rating        REAL,
    helpful       INT DEFAULT 0,
    review_date   TEXT,
    raw           JSONB NOT NULL DEFAULT '{{}}'::jsonb,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_reviews_game ON reviews(game_id);
CREATE INDEX IF NOT EXISTS idx_reviews_platform ON reviews(platform);

CREATE TABLE IF NOT EXISTS review_labels (
    review_id        TEXT PRIMARY KEY REFERENCES reviews(review_id) ON DELETE CASCADE,
    sentiment        TEXT,             -- positive / negative / neutral / mixed
    topics           JSONB NOT NULL DEFAULT '[]'::jsonb,
    aspects          JSONB NOT NULL DEFAULT '{{}}'::jsonb,
    intent           TEXT,
    spam_probability REAL,
    label_source     TEXT NOT NULL DEFAULT 'llm',   -- llm / rule
    model            TEXT,
    labeled_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS review_embeddings (
    review_id   TEXT PRIMARY KEY REFERENCES reviews(review_id) ON DELETE CASCADE,
    embedding   vector({dim}) NOT NULL,
    model       TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_review_embeddings_hnsw
    ON review_embeddings USING hnsw (embedding vector_cosine_ops);

CREATE TABLE IF NOT EXISTS noise_flags (
    id          BIGSERIAL PRIMARY KEY,
    review_id   TEXT NOT NULL REFERENCES reviews(review_id) ON DELETE CASCADE,
    flag_type   TEXT NOT NULL,        -- duplicate / near_duplicate / burst / template / short / rating_only / llm_fake
    reason      TEXT,
    confidence  REAL DEFAULT 0.0,
    detector    TEXT NOT NULL DEFAULT 'rule',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (review_id, flag_type)
);
CREATE INDEX IF NOT EXISTS idx_noise_flags_review ON noise_flags(review_id);

CREATE TABLE IF NOT EXISTS metrics (
    id          BIGSERIAL PRIMARY KEY,
    game_id     TEXT NOT NULL,
    platform    TEXT NOT NULL DEFAULT 'steam',
    metric_date TEXT,
    metric_type TEXT NOT NULL,
    value       REAL,
    raw         JSONB NOT NULL DEFAULT '{{}}'::jsonb,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (game_id, platform, metric_date, metric_type)
);

-- RLS: 默认不给 anon/authenticated 任何行访问;后端用 owner/service_role 连接可绕过。
ALTER TABLE games            ENABLE ROW LEVEL SECURITY;
ALTER TABLE reviews          ENABLE ROW LEVEL SECURITY;
ALTER TABLE review_labels    ENABLE ROW LEVEL SECURITY;
ALTER TABLE review_embeddings ENABLE ROW LEVEL SECURITY;
ALTER TABLE noise_flags      ENABLE ROW LEVEL SECURITY;
ALTER TABLE metrics          ENABLE ROW LEVEL SECURITY;
"""


def ensure_schema(dim: Optional[int] = None) -> Dict[str, Any]:
    """Create extension/tables/indexes idempotently. Returns summary."""
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(schema_sql(dim))
        conn.commit()
    return {"ok": True, "dim": dim or embedding_dim(), "url_host": _url_host()}


def _url_host() -> str:
    url = database_url()
    try:
        return url.split("@")[-1].split("/")[0]
    except Exception:
        return "?"


def schema_dim() -> Optional[int]:
    """Detect the vector dimension of review_embeddings, or None."""
    try:
        with connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT atttypmod FROM pg_attribute WHERE attrelid = 'review_embeddings'::regclass AND attname = 'embedding'"
                )
                row = cur.fetchone()
                if not row:
                    return None
                # vector typmod = dim + 4 (header)
                return int(row[0]) - 4
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Upserts
# ---------------------------------------------------------------------------

def _exec_many(sql: str, rows: Iterable[Tuple], page: int = 500) -> int:
    count = 0
    batch = []
    with connect() as conn:
        with conn.cursor() as cur:
            for row in rows:
                batch.append(row)
                if len(batch) >= page:
                    cur.executemany(sql, batch)
                    count += len(batch)
                    batch = []
            if batch:
                cur.executemany(sql, batch)
                count += len(batch)
        conn.commit()
    return count


def upsert_games(games: Iterable[Dict[str, Any]]) -> int:
    sql = """
    INSERT INTO games (game_id, platform, name, genre, metadata, updated_at)
    VALUES (%s, %s, %s, %s, %s, now())
    ON CONFLICT (game_id) DO UPDATE SET
        name = EXCLUDED.name, genre = EXCLUDED.genre,
        metadata = EXCLUDED.metadata, updated_at = now()
    """
    rows = [
        (
            g["game_id"],
            g.get("platform", "steam"),
            g.get("name", g["game_id"]),
            g.get("genre"),
            json.dumps(g.get("metadata") or {}, ensure_ascii=False),
        )
        for g in games
    ]
    return _exec_many(sql, rows)


def upsert_reviews(reviews: Iterable[Dict[str, Any]]) -> int:
    sql = """
    INSERT INTO reviews (review_id, game_id, platform, username, author, title,
                         content, lang, rating, helpful, review_date, raw)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (review_id) DO UPDATE SET
        content = EXCLUDED.content, rating = EXCLUDED.rating,
        review_date = EXCLUDED.review_date, raw = EXCLUDED.raw
    """
    rows = [
        (
            r["review_id"],
            r["game_id"],
            r.get("platform", "steam"),
            r.get("username"),
            r.get("author"),
            r.get("title"),
            r.get("content", ""),
            r.get("lang"),
            r.get("rating"),
            r.get("helpful", 0),
            r.get("review_date"),
            json.dumps(r.get("raw") or {}, ensure_ascii=False),
        )
        for r in reviews
    ]
    return _exec_many(sql, rows)


def upsert_labels(labels: Iterable[Dict[str, Any]]) -> int:
    sql = """
    INSERT INTO review_labels (review_id, sentiment, topics, aspects, intent,
                               spam_probability, label_source, model, labeled_at)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, now())
    ON CONFLICT (review_id) DO UPDATE SET
        sentiment = EXCLUDED.sentiment, topics = EXCLUDED.topics,
        aspects = EXCLUDED.aspects, intent = EXCLUDED.intent,
        spam_probability = EXCLUDED.spam_probability,
        label_source = EXCLUDED.label_source, model = EXCLUDED.model,
        labeled_at = now()
    """
    rows = [
        (
            l["review_id"],
            l.get("sentiment"),
            json.dumps(l.get("topics") or [], ensure_ascii=False),
            json.dumps(l.get("aspects") or {}, ensure_ascii=False),
            l.get("intent"),
            l.get("spam_probability"),
            l.get("label_source", "llm"),
            l.get("model"),
        )
        for l in labels
    ]
    return _exec_many(sql, rows)


def upsert_embeddings(rows: Iterable[Dict[str, Any]]) -> int:
    sql = """
    INSERT INTO review_embeddings (review_id, embedding, model)
    VALUES (%s, %s::vector, %s)
    ON CONFLICT (review_id) DO UPDATE SET
        embedding = EXCLUDED.embedding, model = EXCLUDED.model, created_at = now()
    """
    data = [
        (r["review_id"], _vec_to_string(r["embedding"]), r.get("model", ""))
        for r in rows
    ]
    return _exec_many(sql, data)


def upsert_noise_flags(flags: Iterable[Dict[str, Any]]) -> int:
    sql = """
    INSERT INTO noise_flags (review_id, flag_type, reason, confidence, detector)
    VALUES (%s, %s, %s, %s, %s)
    ON CONFLICT (review_id, flag_type) DO UPDATE SET
        reason = EXCLUDED.reason, confidence = EXCLUDED.confidence,
        detector = EXCLUDED.detector, created_at = now()
    """
    data = [
        (
            f["review_id"],
            f["flag_type"],
            f.get("reason"),
            f.get("confidence", 0.0),
            f.get("detector", "rule"),
        )
        for f in flags
    ]
    return _exec_many(sql, data)


def upsert_metrics(rows: Iterable[Dict[str, Any]]) -> int:
    sql = """
    INSERT INTO metrics (game_id, platform, metric_date, metric_type, value, raw)
    VALUES (%s, %s, %s, %s, %s, %s)
    ON CONFLICT (game_id, platform, metric_date, metric_type) DO UPDATE SET
        value = EXCLUDED.value, raw = EXCLUDED.raw, created_at = now()
    """
    data = [
        (
            m["game_id"],
            m.get("platform", "steam"),
            m.get("metric_date"),
            m["metric_type"],
            m.get("value"),
            json.dumps(m.get("raw") or {}, ensure_ascii=False),
        )
        for m in rows
    ]
    return _exec_many(sql, data)


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------

def _vec_to_string(vector: Iterable[float]) -> str:
    return "[" + ",".join(str(float(x)) for x in vector) + "]"


def semantic_search(
    query_vector: Iterable[float],
    *,
    game_id: Optional[str] = None,
    platform: Optional[str] = None,
    exclude_noise: bool = True,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """Top-N most similar reviews by cosine distance (pgvector)."""
    sql = """
    SELECT r.review_id, r.game_id, r.platform, r.author, r.content, r.rating,
           r.review_date, l.sentiment, l.topics,
           (1 - (re.embedding <=> %s::vector)) AS similarity
    FROM review_embeddings re
    JOIN reviews r ON r.review_id = re.review_id
    LEFT JOIN review_labels l ON l.review_id = r.review_id
    WHERE 1=1
    """
    params: List[Any] = [_vec_to_string(query_vector)]
    if game_id:
        sql += " AND r.game_id = %s"
        params.append(game_id)
    if platform:
        sql += " AND r.platform = %s"
        params.append(platform)
    if exclude_noise:
        sql += " AND NOT EXISTS (SELECT 1 FROM noise_flags nf WHERE nf.review_id = r.review_id)"
    sql += " ORDER BY re.embedding <=> %s::vector LIMIT %s"
    params += [_vec_to_string(query_vector), int(limit)]

    with connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
    out = []
    for row in rows:
        d = dict(row)
        try:
            d["topics"] = json.loads(d.get("topics") or "[]")
        except (ValueError, TypeError):
            d["topics"] = []
        d["similarity"] = round(float(d.get("similarity") or 0.0), 4)
        out.append(d)
    return out


def get_reviews(
    *,
    game_id: Optional[str] = None,
    platform: Optional[str] = None,
    exclude_noise: bool = True,
    limit: int = 200,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    sql = """
    SELECT r.review_id, r.game_id, r.platform, r.author, r.content, r.rating,
           r.review_date, l.sentiment, l.topics, l.intent, l.spam_probability
    FROM reviews r
    LEFT JOIN review_labels l ON l.review_id = r.review_id
    WHERE 1=1
    """
    params: List[Any] = []
    if game_id:
        sql += " AND r.game_id = %s"
        params.append(game_id)
    if platform:
        sql += " AND r.platform = %s"
        params.append(platform)
    if exclude_noise:
        sql += " AND NOT EXISTS (SELECT 1 FROM noise_flags nf WHERE nf.review_id = r.review_id)"
    sql += " ORDER BY r.created_at DESC LIMIT %s OFFSET %s"
    params += [int(limit), int(offset)]

    with connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
    out = []
    for row in rows:
        d = dict(row)
        try:
            d["topics"] = json.loads(d.get("topics") or "[]")
        except (ValueError, TypeError):
            d["topics"] = []
        out.append(d)
    return out


def noise_summary() -> List[Dict[str, Any]]:
    """Counts of noise flags by type."""
    sql = """
    SELECT flag_type, COUNT(*) AS count, ROUND(AVG(confidence)::numeric, 2) AS avg_confidence
    FROM noise_flags GROUP BY flag_type ORDER BY count DESC
    """
    with connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql)
            return [dict(r) for r in cur.fetchall()]

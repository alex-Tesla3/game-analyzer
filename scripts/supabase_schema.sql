-- Game Analyzer AI 管道 schema (在 Supabase SQL Editor 中执行一次)
-- 幂等: 可重复执行

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS games (
    game_id      TEXT PRIMARY KEY,
    platform     TEXT NOT NULL DEFAULT 'steam',
    name         TEXT NOT NULL,
    genre        TEXT,
    metadata     JSONB NOT NULL DEFAULT '{}'::jsonb,
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
    raw           JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_reviews_game ON reviews(game_id);
CREATE INDEX IF NOT EXISTS idx_reviews_platform ON reviews(platform);

CREATE TABLE IF NOT EXISTS review_labels (
    review_id        TEXT PRIMARY KEY REFERENCES reviews(review_id) ON DELETE CASCADE,
    sentiment        TEXT,             -- positive / negative / neutral / mixed
    topics           JSONB NOT NULL DEFAULT '[]'::jsonb,
    aspects          JSONB NOT NULL DEFAULT '{}'::jsonb,
    intent           TEXT,
    spam_probability REAL,
    label_source     TEXT NOT NULL DEFAULT 'llm',   -- llm / rule
    model            TEXT,
    labeled_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS review_embeddings (
    review_id   TEXT PRIMARY KEY REFERENCES reviews(review_id) ON DELETE CASCADE,
    embedding   vector(1536) NOT NULL,
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
    raw         JSONB NOT NULL DEFAULT '{}'::jsonb,
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

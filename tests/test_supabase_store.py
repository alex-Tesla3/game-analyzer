"""Supabase 存储层测试(离线: schema 生成/向量字符串/开关)。"""

from __future__ import annotations

from src.services.supabase_store import (
    _vec_to_string,
    embedding_dim,
    enabled,
    schema_sql,
)


def test_enabled_false_without_url(monkeypatch):
    monkeypatch.delenv("SUPABASE_DATABASE_URL", raising=False)
    assert enabled() is False


def test_schema_sql_contains_pgvector_and_rls(monkeypatch):
    monkeypatch.setenv("EMBEDDING_DIM", "1536")
    sql = schema_sql()
    assert "CREATE EXTENSION IF NOT EXISTS vector" in sql
    assert "vector(1536)" in sql
    assert "ENABLE ROW LEVEL SECURITY" in sql
    assert "USING hnsw (embedding vector_cosine_ops)" in sql
    for table in ("reviews", "review_labels", "review_embeddings", "noise_flags", "games", "metrics"):
        assert f"CREATE TABLE IF NOT EXISTS {table}" in sql


def test_vec_to_string():
    assert _vec_to_string([1.0, 0.5, -2]) == "[1.0,0.5,-2.0]"


def test_embedding_dim_env(monkeypatch):
    monkeypatch.setenv("EMBEDDING_DIM", "768")
    assert embedding_dim() == 768

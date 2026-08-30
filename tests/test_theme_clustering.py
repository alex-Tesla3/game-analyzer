"""评论聚类 + LLM 主题提炼测试。"""

from __future__ import annotations

import pytest

from src.services.theme_clustering import (
    _extract_json_object,
    choose_k,
    cluster_reviews,
    kmeans,
    llm_theme_for_cluster,
)


def test_choose_k():
    assert choose_k(0) == 0
    assert choose_k(6) == 2
    assert choose_k(100) == 6  # 上限


def test_kmeans_separates():
    vectors = [[1.0, 0.0], [0.99, 0.01], [0.0, 1.0], [0.01, 0.99]]
    labels, centers = kmeans(vectors, k=2)
    assert len(set(labels)) == 2
    assert labels[0] == labels[1] and labels[2] == labels[3]


def test_cluster_reviews():
    reviews = [
        {"review_id": "a", "game_id": "10", "content": "x"},
        {"review_id": "b", "game_id": "10", "content": "y"},
        {"review_id": "c", "game_id": "10", "content": "z"},
    ]
    embeddings = {"a": [1.0, 0.0], "b": [0.99, 0.01], "c": [0.0, 1.0]}
    clusters = cluster_reviews(reviews, embeddings, k=2)
    assert len(clusters) == 2
    total_members = sum(c["member_count"] for c in clusters)
    assert total_members == 3
    assert all(c["representative_review_id"] for c in clusters)


@pytest.mark.asyncio
async def test_llm_theme_fallback_when_llm_down(monkeypatch):
    async def fake(prompt, **kwargs):
        raise RuntimeError("down")

    import src.services.llm_client as llm
    monkeypatch.setattr(llm, "complete_prompt", fake)

    cluster = {"cluster_id": "clu_1", "member_ids": ["a", "b"]}
    reviews = [
        {"review_id": "a", "content": "Too many cheaters, unplayable"},
        {"review_id": "b", "content": "Matchmaking is full of hackers"},
    ]
    theme = await llm_theme_for_cluster(reviews, cluster)
    assert theme["theme_name"]  # fallback 非空


@pytest.mark.asyncio
async def test_llm_theme_parses(monkeypatch):
    async def fake(prompt, **kwargs):
        return '{"theme_name":"反作弊问题","description":"匹配内挂太多","key_issues":["外挂多"]}'

    import src.services.llm_client as llm
    monkeypatch.setattr(llm, "complete_prompt", fake)

    cluster = {"cluster_id": "clu_1", "member_ids": ["a"]}
    reviews = [{"review_id": "a", "content": "Too many cheaters"}]
    theme = await llm_theme_for_cluster(reviews, cluster)
    assert theme["theme_name"] == "反作弊问题"
    assert theme["key_issues"] == ["外挂多"]


def test_extract_json_object():
    assert _extract_json_object('xx {"a":1} yy') == {"a": 1}
    assert _extract_json_object("no json") is None

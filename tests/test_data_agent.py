"""数据 Agent 管道测试(离线降级: 无 Supabase / 无 LLM)。"""

from __future__ import annotations

import json

import pytest

from src.services.data_agent import (
    normalize_review,
    review_content,
    review_product,
    run_data_agent,
    stable_review_id,
)


def _dataset(tmp_path):
    data = {
        "source": "test",
        "app_ids": ["10"],
        "games": [{"app_id": "10", "name": "Counter-Strike"}],
        "comments": [
            {"product": "10", "product_name": "Counter-Strike", "platform": "Steam", "内容": "Great team game."},
            {"product": "10", "platform": "Steam", "内容": "Great team game."},
            {"product": "10", "platform": "Steam", "内容": "good"},
            {"product": "10", "platform": "Steam", "内容": "画面很好,手感不错,强烈推荐"},
        ],
        "metrics": [{"product": "10", "platform": "Steam", "metric": "抓取评论数", "值": 4}],
    }
    path = tmp_path / "steam_dataset.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return str(path), data


def test_normalize_fields():
    review = {"product": "10", "platform": "Steam", "内容": "nice", "评分": 4, "作者": "u"}
    norm = normalize_review(review)
    assert review_content(norm) == "nice"
    assert review_product(norm) == "10"
    assert norm["platform"] == "steam"
    assert norm["rating"] == 4.0
    assert norm["review_id"] == stable_review_id(review)


@pytest.mark.asyncio
async def test_run_agent_offline(tmp_path, monkeypatch):
    monkeypatch.delenv("SUPABASE_DATABASE_URL", raising=False)
    monkeypatch.delenv("EMBEDDING_MODEL", raising=False)
    path, _ = _dataset(tmp_path)

    async def fake_embed(texts):
        return [[float(i + 1), 0.0] for i in range(len(texts))]

    import src.services.llm_client as llm
    monkeypatch.setattr(llm, "embed_texts", fake_embed)
    monkeypatch.setenv("EMBEDDING_DIM", "2")

    report = await run_data_agent("", dataset_path=path, steps=["clean", "label", "embed", "store", "aggregate"], use_llm=False)
    assert report["success"] is True
    assert report["source_reviews"] == 4
    assert report["aggregate"]["clean_reviews"] == 1  # 3 条被标记噪音
    assert report["steps"]["store"]["error"]  # supabase 未配置

    saved = json.load(open(path, encoding="utf-8"))
    comments = saved["comments"]
    assert comments[0]["is_noise"] is True      # duplicate
    assert comments[2]["is_noise"] is True      # short
    assert comments[3]["is_noise"] is False
    assert "label" in comments[3]


@pytest.mark.asyncio
async def test_run_agent_missing_dataset(tmp_path, monkeypatch):
    monkeypatch.delenv("SUPABASE_DATABASE_URL", raising=False)
    report = await run_data_agent("", dataset_path="/tmp/definitely_missing_dataset.json", steps=["aggregate"])
    assert report["success"] is False

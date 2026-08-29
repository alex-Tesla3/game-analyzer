"""噪音/水军检测测试(规则 + 向量 + LLM 复核)。"""

from __future__ import annotations

import pytest

from src.services.noise_detector import (
    _cosine,
    apply_noise_flags,
    detect_noise,
    llm_verify_flags,
)


def _review(rid, content, author="u1", game="10", rating=1, date=""):
    return {
        "review_id": rid,
        "game_id": game,
        "content": content,
        "author": author,
        "rating": rating,
        "review_date": date,
    }


@pytest.mark.asyncio
async def test_detect_duplicate_short_rating_only():
    reviews = [
        _review("a", "Great team game.", author="alice"),
        _review("b", "Great team game.", author="bob"),          # duplicate
        _review("c", "good"),                                    # short template
        _review("d", "", rating=1),                              # rating only
        _review("e", "This is a long genuine review with details."),
    ]
    flags = await detect_noise(reviews, use_llm=False)
    by = {(f["review_id"], f["flag_type"]): f for f in flags}
    assert ("a", "duplicate") in by
    assert ("b", "duplicate") in by
    assert ("c", "short") in by
    assert ("d", "rating_only") in by
    assert ("e", "duplicate") not in by


@pytest.mark.asyncio
async def test_detect_burst():
    reviews = [_review(f"r{i}", f"review {i} content", author="spammer") for i in range(5)]
    flags = await detect_noise(reviews, use_llm=False)
    burst = [f for f in flags if f["flag_type"] == "burst"]
    assert len(burst) == 5


def test_embedding_near_duplicate():
    reviews = [
        _review("x", "Very fun game, love the gameplay loop."),
        _review("y", "Very fun game, love the gameplay loop!"),
        _review("z", "The graphics are amazing and detailed."),
    ]
    emb = {
        "x": [1.0, 0.0, 0.0],
        "y": [0.99, 0.01, 0.0],
        "z": [0.0, 1.0, 0.0],
    }
    import asyncio
    flags = asyncio.run(detect_noise(reviews, embeddings=emb, use_llm=False))
    near = {(f["review_id"], f["flag_type"]) for f in flags}
    assert ("x", "near_duplicate") in near
    assert ("y", "near_duplicate") in near
    assert ("z", "near_duplicate") not in near


def test_apply_flags_to_reviews():
    reviews = [_review("a", "content"), _review("b", "content")]
    flags = [{"review_id": "a", "flag_type": "short", "reason": "短", "confidence": 0.8, "detector": "rule"}]
    apply_noise_flags(reviews, flags)
    assert reviews[0]["is_noise"] is True
    assert reviews[1]["is_noise"] is False
    assert "短" in reviews[0]["noise_reasons"]


def test_cosine():
    assert _cosine([1.0, 0.0], [1.0, 0.0]) == 1.0
    assert _cosine([1.0, 0.0], [0.0, 1.0]) == 0.0


@pytest.mark.asyncio
async def test_llm_verify_flags_parse(monkeypatch):
    async def fake_complete(prompt, **kwargs):
        return '[{"index":0,"is_fake":true,"reason":"刷评","confidence":0.95}]'

    import src.services.llm_client as llm
    monkeypatch.setattr(llm, "complete_prompt", fake_complete)

    reviews = [_review("a", "Great team game."), _review("b", "normal content here")]
    flags = [{"review_id": "a", "flag_type": "short", "reason": "短", "confidence": 0.8, "detector": "rule"}]
    out = await llm_verify_flags(reviews, flags)
    assert len(out) == 1
    assert out[0]["review_id"] == "a"
    assert out[0]["flag_type"] == "llm_fake"

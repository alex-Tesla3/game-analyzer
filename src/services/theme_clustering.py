"""基于 embedding 的评论聚类 + LLM 主题提炼。

流程: 向量化(已在 embed 步骤完成) -> KMeans 聚类 -> 每个簇选代表评论 ->
      LLM 提炼主题(名称/描述/关键问题) -> 落库 theme_clusters
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Sequence

import numpy as np


def choose_k(n: int, max_k: int = 6) -> int:
    """启发式簇数: sqrt(n/2), 上限 max_k, 至少 1。"""
    if n <= 0:
        return 0
    return max(1, min(max_k, int(round((n / 2) ** 0.5))))


def kmeans(vectors: Sequence[Sequence[float]], k: int, max_iter: int = 60, seed: int = 42):
    """纯 numpy KMeans。返回 (labels, centers)。"""
    X = np.asarray(vectors, dtype=float)
    n = len(X)
    k = max(1, min(k, n))
    rng = np.random.default_rng(seed)
    centers = X[rng.choice(n, k, replace=False)].copy()
    labels = np.zeros(n, dtype=int)
    for _ in range(max_iter):
        d = ((X[:, None, :] - centers[None, :, :]) ** 2).sum(-1)
        labels = d.argmin(1)
        new_centers = np.array(
            [
                X[labels == c].mean(0) if np.any(labels == c) else centers[c]
                for c in range(k)
            ]
        )
        if np.allclose(new_centers, centers, atol=1e-6):
            break
        centers = new_centers
    return labels.tolist(), centers


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if not na or not nb:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def cluster_reviews(
    reviews: Sequence[Dict[str, Any]],
    embeddings: Dict[str, List[float]],
    k: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """把有向量的评论聚类, 返回 [{cluster_id, member_ids[], representative, member_count, avg_similarity}]。"""
    items = [(r["review_id"], r) for r in reviews if r.get("review_id") in embeddings]
    if not items:
        return []
    vectors = [embeddings[rid] for rid, _ in items]
    k = k or choose_k(len(items))
    labels, centers = kmeans(vectors, k)

    clusters: Dict[int, Dict[str, Any]] = {}
    for idx, (rid, review) in enumerate(items):
        cid = int(labels[idx])
        cluster = clusters.setdefault(
            cid,
            {
                "cluster_id": f"clu_{cid + 1}",
                "game_id": review.get("game_id", ""),
                "member_ids": [],
                "member_count": 0,
                "avg_similarity": 0.0,
            },
        )
        cluster["member_ids"].append(rid)

    out = []
    for cid, cluster in sorted(clusters.items()):
        member_ids = cluster["member_ids"]
        sims = [_cosine(np.asarray(embeddings[rid]), centers[cid]) for rid in member_ids]
        avg_sim = float(np.mean(sims)) if sims else 0.0
        rep_idx = int(np.argmax(sims))
        out.append({
            "cluster_id": cluster["cluster_id"],
            "game_id": cluster["game_id"],
            "member_ids": member_ids,
            "representative_review_id": member_ids[rep_idx],
            "member_count": len(member_ids),
            "avg_similarity": round(avg_sim, 4),
        })
    return out


_THEME_PROMPT = """你是游戏玩家洞察分析师。下面是一组语义相近的玩家评论(聚类簇)。
请用中文总结这个簇的【主题】, 输出严格 JSON, 不要其他文字:
{"theme_name":"简短主题(<=12字)","description":"一句话描述(<=40字)","key_issues":["关键问题1","关键问题2"]}

评论:
{items}"""


async def llm_theme_for_cluster(
    reviews: Sequence[Dict[str, Any]],
    cluster: Dict[str, Any],
) -> Dict[str, Any]:
    """LLM 提炼单个簇的主题; 失败时回退到代表评论。"""
    member_ids = cluster.get("member_ids") or []
    by_id = {r.get("review_id"): r for r in reviews}
    items = []
    for rid in member_ids:
        review = by_id.get(rid)
        if review:
            content = (review.get("content") or "")[:200]
            if content:
                items.append(content)
        if len(items) >= 8:
            break
    fallback = {
        "theme_name": f"簇 {cluster['cluster_id']}",
        "description": (items[0] or "")[:40] if items else "",
        "key_issues": [],
    }
    if not items:
        return fallback
    try:
        from src.services.llm_client import complete_prompt

        raw = await complete_prompt(
            _THEME_PROMPT.replace("{items}", json.dumps(items, ensure_ascii=False)),
            max_tokens=300,
        )
        data = _extract_json_object(raw)
        if not data:
            return fallback
        return {
            "theme_name": str(data.get("theme_name") or fallback["theme_name"])[:20],
            "description": str(data.get("description") or fallback["description"])[:60],
            "key_issues": [str(x)[:60] for x in (data.get("key_issues") or [])][:6],
        }
    except Exception:
        return fallback


def _extract_json_object(text: str) -> Optional[Dict[str, Any]]:
    text = text.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        data = json.loads(text[start : end + 1])
        return data if isinstance(data, dict) else None
    except ValueError:
        return None

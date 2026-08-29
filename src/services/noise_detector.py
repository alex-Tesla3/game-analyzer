"""水军/噪音评论检测。

三层检测:
1. 规则层  — 重复文本、超短模板、纯评分、同账号爆发式刷评
2. 向量层  — embedding 余弦相似度过高 -> 近似重复/模板簇
3. LLM 层  — 对可疑评论做人工级复核(可选,需 LLM 可用)

输出: 每条噪音标记 {review_id, flag_type, reason, confidence, detector}
"""

from __future__ import annotations

import asyncio
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple

# 极短/泛化模板评论文本(常见于水军)
_GENERIC_SHORT = {
    "好玩", "垃圾", "不错", "太棒了", "一般般", "good game", "nice game",
    "great", "nice", "good", "bad", "love it", "hate it", "推荐", "不推荐",
    "666", "顶", "支持", "差评", "好评", "10/10", "1/10",
}
_MIN_TEXT_LEN = 12          # 去除空白后低于此长度的纯文本视为"短"
_NEAR_DUP_THRESHOLD = 0.92  # embedding 余弦相似度阈值
_BURST_MIN_TOTAL = 5        # 同作者同游戏评论总数阈值
_BURST_MIN_WINDOW = 3       # 同作者 24h 内评论数阈值


def normalize_text(text: str) -> str:
    return re.sub(r"[\s\W_]+", "", (text or "").lower())


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    if not na or not nb:
        return 0.0
    return dot / (na * nb)


# ---------------------------------------------------------------------------
# 规则层
# ---------------------------------------------------------------------------

def _rule_flags(reviews: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    flags: List[Dict[str, Any]] = []
    by_key: Dict[str, List[Tuple[int, Dict[str, Any]]]] = defaultdict(list)

    for idx, review in enumerate(reviews):
        review_id = review.get("review_id") or review.get("id") or f"rev_{idx}"
        content = review.get("content") or review.get("text") or ""
        norm = normalize_text(content)

        # 纯评分无文本
        if not content.strip() and review.get("rating") is not None:
            flags.append({"review_id": review_id, "flag_type": "rating_only",
                          "reason": "纯评分无文本", "confidence": 0.9, "detector": "rule"})

        # 超短模板
        elif 0 < len(norm) < _MIN_TEXT_LEN or norm in _GENERIC_SHORT:
            flags.append({"review_id": review_id, "flag_type": "short",
                          "reason": f"内容过短/模板化(长度 {len(norm)})", "confidence": 0.8, "detector": "rule"})

        key = (review.get("game_id") or review.get("product") or "", norm)
        if norm:
            by_key[key].append((idx, review))

    # 完全相同文本 -> duplicate
    for (game, norm), items in by_key.items():
        if len(items) >= 2:
            for idx, review in items:
                review_id = review.get("review_id") or review.get("id") or f"rev_{idx}"
                flags.append({"review_id": review_id, "flag_type": "duplicate",
                              "reason": f"同游戏重复文本(出现 {len(items)} 次)", "confidence": 0.95,
                              "detector": "rule"})

    # 同作者爆发式刷评
    author_groups: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    for review in reviews:
        author = (review.get("author") or review.get("user") or "").strip()
        game = review.get("game_id") or review.get("product") or ""
        if author:
            author_groups[(author, game)].append(review)
    for (author, game), group in author_groups.items():
        if len(group) >= _BURST_MIN_TOTAL:
            for review in group:
                rid = review.get("review_id") or review.get("id") or ""
                if rid:
                    flags.append({"review_id": rid, "flag_type": "burst",
                                  "reason": f"同一作者在 {game or '同游戏'} 发布 {len(group)} 条评论",
                                  "confidence": 0.85, "detector": "rule"})
        # 24h 窗口
        if len(group) >= _BURST_MIN_WINDOW:
            dates = []
            for review in group:
                d = review.get("review_date") or review.get("date") or review.get("timestamp") or ""
                try:
                    dates.append(datetime.fromisoformat(str(d).replace("Z", "+00:00")))
                except (ValueError, TypeError):
                    pass
            dates.sort()
            for i in range(len(dates)):
                for j in range(i + 1, len(dates)):
                    if (dates[j] - dates[i]).total_seconds() <= 24 * 3600 and j - i + 1 >= _BURST_MIN_WINDOW:
                        for review in group[i : j + 1]:
                            rid = review.get("review_id") or review.get("id") or ""
                            if rid:
                                flags.append({"review_id": rid, "flag_type": "burst",
                                              "reason": "同一作者 24h 内集中发布多条评论",
                                              "confidence": 0.8, "detector": "rule"})
                        break
                else:
                    continue
                break
    return flags


# ---------------------------------------------------------------------------
# 向量层
# ---------------------------------------------------------------------------

def _embedding_flags(
    reviews: Sequence[Dict[str, Any]],
    embeddings: Optional[Dict[str, List[float]]],
    max_sample: int = 400,
) -> List[Dict[str, Any]]:
    if not embeddings:
        return []
    flags: List[Dict[str, Any]] = []
    indexed: List[Tuple[str, List[float]]] = []
    for review in reviews:
        rid = review.get("review_id") or review.get("id") or ""
        vec = (embeddings or {}).get(rid) or (embeddings or {}).get(review.get("review_id") or review.get("id") or "")
        if rid and vec:
            indexed.append((rid, vec))
    if len(indexed) > max_sample:
        indexed = indexed[:max_sample]
    for i in range(len(indexed)):
        rid_i, vec_i = indexed[i]
        for j in range(i + 1, len(indexed)):
            rid_j, vec_j = indexed[j]
            sim = _cosine(vec_i, vec_j)
            if sim >= _NEAR_DUP_THRESHOLD:
                reason = f"与 {rid_j} 近似重复(相似度 {sim:.2f})"
                flags.append({"review_id": rid_i, "flag_type": "near_duplicate",
                              "reason": reason, "confidence": min(0.99, sim), "detector": "embedding"})
                flags.append({"review_id": rid_j, "flag_type": "near_duplicate",
                              "reason": f"与 {rid_i} 近似重复(相似度 {sim:.2f})",
                              "confidence": min(0.99, sim), "detector": "embedding"})
    return flags


# ---------------------------------------------------------------------------
# LLM 复核层
# ---------------------------------------------------------------------------

_VERDICT_PROMPT = """你是游戏评论质量审核员。判断下面每条评论是否为"水军/机器人/刷评/无关广告"。
只输出 JSON 数组，不要其他文字，格式:
[{"index":0,"is_fake":true,"reason":"短评","confidence":0.9}, ...]

评论列表:
{items}"""


async def llm_verify_flags(
    reviews: Sequence[Dict[str, Any]],
    flags: Sequence[Dict[str, Any]],
    *,
    max_items: int = 60,
) -> List[Dict[str, Any]]:
    """对可疑评论调用 LLM 复核, 产出 detector='llm' 的标记。"""
    from src.services.llm_client import complete_prompt

    flagged_ids = {f["review_id"] for f in flags if f.get("detector") == "rule"}
    if not flagged_ids:
        return []
    items = []
    for review in reviews:
        rid = review.get("review_id") or review.get("id") or ""
        if rid in flagged_ids and len(items) < max_items:
            content = (review.get("content") or review.get("text") or "")[:400]
            items.append({"index": len(items), "review_id": rid, "content": content})
    if not items:
        return []
    prompt = _VERDICT_PROMPT.replace("{items}", json.dumps(items, ensure_ascii=False)[:6000])
    try:
        raw = await complete_prompt(prompt, max_tokens=1000)
    except Exception:
        return []  # LLM 不可用 -> 静默降级

    verdicts = _extract_json_array(raw)
    out = []
    for verdict in verdicts:
        try:
            idx = int(verdict.get("index"))
            item = items[idx]
        except (ValueError, TypeError, IndexError):
            continue
        if verdict.get("is_fake"):
            out.append({
                "review_id": item["review_id"],
                "flag_type": "llm_fake",
                "reason": str(verdict.get("reason") or "LLM 判定为水军/刷评"),
                "confidence": float(verdict.get("confidence") or 0.7),
                "detector": "llm",
            })
    return out


def _extract_json_array(text: str) -> List[Dict[str, Any]]:
    text = text.strip()
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1 or end <= start:
        return []
    try:
        data = json.loads(text[start : end + 1])
        return data if isinstance(data, list) else []
    except ValueError:
        return []


# ---------------------------------------------------------------------------
# 汇总入口
# ---------------------------------------------------------------------------

async def detect_noise(
    reviews: Sequence[Dict[str, Any]],
    embeddings: Optional[Dict[str, List[float]]] = None,
    *,
    use_llm: bool = True,
    max_llm_items: int = 60,
) -> List[Dict[str, Any]]:
    """运行全部检测, 返回去重后的噪音标记列表。"""
    flags = _rule_flags(reviews) + _embedding_flags(reviews, embeddings)
    if use_llm:
        try:
            flags += await llm_verify_flags(reviews, flags, max_items=max_llm_items)
        except Exception:
            pass
    # 去重: 同 review_id+flag_type 保留最高 confidence
    best: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for flag in flags:
        key = (flag["review_id"], flag["flag_type"])
        if key not in best or flag.get("confidence", 0) > best[key].get("confidence", 0):
            best[key] = flag
    return list(best.values())


def apply_noise_flags(
    reviews: Sequence[Dict[str, Any]],
    flags: Sequence[Dict[str, Any]],
) -> None:
    """把 is_noise / noise_reasons 写回评论 dict(原地修改)。"""
    by_id: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for flag in flags:
        by_id[flag["review_id"]].append(flag)
    for review in reviews:
        rid = review.get("review_id") or review.get("id") or ""
        review_flags = by_id.get(rid, [])
        review["is_noise"] = bool(review_flags)
        review["noise_reasons"] = [f.get("reason") for f in review_flags]
        review["noise_flags"] = [f.get("flag_type") for f in review_flags]

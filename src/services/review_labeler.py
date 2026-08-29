"""LLM 评论标签(情感/主题/游戏维度/意图), 带规则回退。

LLM 可用时输出结构化 JSON; 不可用/失败时回退到关键词规则,
保证管道在任何环境下都能产出标签。
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any, Dict, List, Optional, Sequence

_LABEL_PROMPT = """你是游戏用户评论分析专家。为每条评论生成结构化标签。
只输出 JSON 数组, 不要其他文字。格式:
[{"index":0,"sentiment":"negative","topics":["performance","matchmaking"],"aspects":{"performance":"差"},"intent":"complaint","spam_probability":0.1}, ...]

sentiment: positive | negative | neutral | mixed
topics 取值(可多个, 也允许自拟): performance, matchmaking, anti-cheat, monetization,
  content, balance, bugs, ui, community, server, gameplay, graphics, story, audio, other
aspects: {"维度": "评价", ...}
intent: recommend | complaint | question | praise | spam | other
spam_probability: 0-1

评论列表:
{items}"""

_TOPIC_KEYWORDS = {
    "performance": ["卡", "fps", "帧", "优化", "掉帧", "卡顿", "lag", "stutter"],
    "matchmaking": ["匹配", "排队", "段位", "elo", "rank", "排位"],
    "anti-cheat": ["外挂", "作弊", "hack", "cheat", "脚本", "挂"],
    "monetization": ["氪金", "付费", "皮肤", "充值", "内购", "pay to win", "p2w"],
    "content": ["内容", "更新", "新地图", "新英雄", "活动", "dlc"],
    "balance": ["平衡", "太强", "太弱", "削弱", "加强", "op"],
    "bugs": ["bug", "崩溃", "闪退", "报错", "卡死", "错误"],
    "ui": ["界面", "ui", "操作", "菜单"],
    "community": ["社区", "玩家", "环境", "喷子", "toxic"],
    "server": ["服务器", "延迟", "掉线", "ping", "断线"],
    "gameplay": ["玩法", "手感", "体验", "枪械", "操作感", "机制"],
    "graphics": ["画面", "画质", "特效", "建模", "材质"],
    "story": ["剧情", "故事", "世界观", "角色"],
    "audio": ["音效", "音乐", "配音", "声音"],
}
_SENTIMENT_NEG = ["差", "烂", "垃圾", "卡", "bug", "挂", "失望", "退款", "坑", "慢", "贵", "恶心", "不好"]
_SENTIMENT_POS = ["好", "棒", "喜欢", "赞", "推荐", "神", "满意", "爽", "爱了", "好玩", "优秀"]


def _rule_label(review: Dict[str, Any]) -> Dict[str, Any]:
    content = (review.get("content") or review.get("text") or "").lower()
    topics = [t for t, words in _TOPIC_KEYWORDS.items() if any(w in content for w in words)]
    pos = sum(w in content for w in _SENTIMENT_POS)
    neg = sum(w in content for w in _SENTIMENT_NEG)
    sentiment = "positive" if pos > neg else ("negative" if neg > pos else "neutral")
    rating = review.get("rating")
    if rating is not None and sentiment == "neutral":
        sentiment = "positive" if rating >= 4 else ("negative" if rating <= 2 else "neutral")
    spam_probability = 0.9 if len(content.strip()) < 12 else 0.1
    return {
        "sentiment": sentiment,
        "topics": topics[:5] or ["other"],
        "aspects": {},
        "intent": "spam" if spam_probability > 0.5 else "other",
        "spam_probability": spam_probability,
        "label_source": "rule",
        "model": "rule",
    }


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


def _clean_topics(topics: Any) -> List[str]:
    if isinstance(topics, list):
        return [str(t)[:30] for t in topics][:8]
    if isinstance(topics, str):
        return [t.strip() for t in re.split(r"[,，、]", topics) if t.strip()][:8]
    return []


async def label_review_batch(
    reviews: Sequence[Dict[str, Any]],
    *,
    model_name: str = "llm",
) -> List[Dict[str, Any]]:
    """为一批评论生成标签; LLM 失败时逐条回退规则。"""
    if not reviews:
        return []
    labels: List[Dict[str, Any]] = []
    llm_ok = False

    try:
        from src.services.llm_client import complete_prompt

        items = []
        for idx, review in enumerate(reviews):
            rid = review.get("review_id") or review.get("id") or f"rev_{idx}"
            items.append({"index": idx, "review_id": rid,
                          "content": (review.get("content") or review.get("text") or "")[:500]})
        raw = await complete_prompt(
            _LABEL_PROMPT.replace("{items}", json.dumps(items, ensure_ascii=False)[:10000]),
            max_tokens=1500,
        )
        verdicts = _extract_json_array(raw)
        if verdicts:
            llm_ok = True
            for verdict in verdicts:
                try:
                    idx = int(verdict.get("index"))
                    item = items[idx]
                except (ValueError, TypeError, IndexError):
                    continue
                rid = item["review_id"]
                labels.append({
                    "review_id": rid,
                    "sentiment": str(verdict.get("sentiment") or "neutral"),
                    "topics": _clean_topics(verdict.get("topics")),
                    "aspects": verdict.get("aspects") if isinstance(verdict.get("aspects"), dict) else {},
                    "intent": str(verdict.get("intent") or "other"),
                    "spam_probability": float(verdict.get("spam_probability") or 0.0),
                    "label_source": "llm",
                    "model": model_name,
                })
    except Exception:
        llm_ok = False

    if not llm_ok:
        for idx, review in enumerate(reviews):
            rid = review.get("review_id") or review.get("id") or f"rev_{idx}"
            rule = _rule_label(review)
            labels.append({"review_id": rid, **rule, "model": model_name})

    # 保证顺序与输入一致(缺失的补规则)
    by_id = {label["review_id"]: label for label in labels}
    ordered = []
    for idx, review in enumerate(reviews):
        rid = review.get("review_id") or review.get("id") or f"rev_{idx}"
        if rid in by_id:
            ordered.append(by_id[rid])
        else:
            rule = _rule_label(review)
            ordered.append({"review_id": rid, **rule, "model": model_name})
    return ordered


async def label_reviews(
    reviews: Sequence[Dict[str, Any]],
    *,
    batch_size: int = 30,
    max_batches: Optional[int] = None,
    on_progress: Optional[callable] = None,
) -> List[Dict[str, Any]]:
    """分批并行打标签(串行调用 LLM 以保证稳定性, 可扩展并发)。"""
    all_labels: List[Dict[str, Any]] = []
    batches = [reviews[i : i + batch_size] for i in range(0, len(reviews), batch_size)]
    if max_batches is not None:
        batches = batches[:max_batches]
    for i, batch in enumerate(batches):
        labels = await label_review_batch(batch, model_name="llm")
        all_labels.extend(labels)
        if on_progress:
            on_progress(min(len(all_labels), len(reviews)), len(reviews))
    return all_labels

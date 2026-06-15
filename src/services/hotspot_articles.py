"""Industry hotspot deep-dive articles from crawled/imported player signals."""

from __future__ import annotations

import json
import re
import uuid
from collections import Counter
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple

from auth import LLM_CONFIG, LLM_PROVIDERS

from database import db_manager
from src.data_resolution import get_user_comments_data, get_user_metrics_data, resolve_user_data_source
from src.mvp_data import get_mvp_analysis, product_matches, record_product
from src.services.engagement_funnel import _comments_for_product, _is_positive_comment, _comment_text
from src.services.llm_client import (
    clean_llm_report_text,
    complete_prompt_with_retry,
    llm_is_configured,
    parse_json_from_llm,
)
from src.services.product_name_resolver import build_product_name_map

_TOPIC_TEMPLATES: List[Dict[str, str]] = [
    {
        "angle": "revenue_decline",
        "title_tpl": "为什么《{name}》新版本流水暴跌？基于 {sample} 条玩家评论的数据起底",
        "hook": "版本更新后收入曲线与舆情是否同向下滑？",
    },
    {
        "angle": "sentiment_crash",
        "title_tpl": "《{name}》口碑滑坡背后：{sample} 条真实玩家在说什么",
        "hook": "好评率与负面主题是否在更新窗口集中爆发？",
    },
    {
        "angle": "patch_backlash",
        "title_tpl": "一次更新引发的增长危机：《{name}》全网评论复盘",
        "hook": "补丁说明与玩家体感是否出现明显错位？",
    },
    {
        "angle": "monetization_backlash",
        "title_tpl": "氪金争议如何拖累《{name}》？评论样本里的商业化信号",
        "hook": "付费、通行证、抽卡相关吐槽是否主导负面声量？",
    },
    {
        "angle": "retention_risk",
        "title_tpl": "《{name}》留存告急？从评论样本看流失前兆",
        "hook": "新手引导、匹配、性能类抱怨是否抬升？",
    },
]

_THEME_KEYWORDS: Dict[str, Tuple[str, ...]] = {
    "平衡性": ("平衡", "nerf", "buff", "削弱", "加强", "meta"),
    "匹配/外挂": ("匹配", "外挂", "作弊", "cheat", "排队", "延迟", "lag"),
    "商业化": ("氪金", "付费", "通行证", "抽卡", "gacha", "pay", "商城", "皮肤"),
    "内容更新": ("更新", "patch", "dlc", "赛季", "内容", "剧情"),
    "性能体验": ("卡顿", "闪退", "优化", "fps", "崩溃", "bug"),
    "新手体验": ("新手", "教程", "引导", "上手", "tutorial"),
}

_NEGATIVE_HINTS = _THEME_KEYWORDS  # alias for readability


def _provider_label() -> str:
    provider = LLM_CONFIG.get("provider") or ""
    return LLM_PROVIDERS.get(provider, {}).get("name", provider)


def _product_label(product_id: str, name_map: Dict[str, str]) -> str:
    return name_map.get(product_id) or str(product_id)


def _now_iso() -> str:
    return datetime.now().isoformat()


class HotspotCustomTopicRepository:
    @staticmethod
    def list_for_user(username: str) -> List[Dict[str, Any]]:
        rows = db_manager.execute(
            """
            SELECT topic_id, username, product_id, title, brief, hook, angle, created_at, updated_at
            FROM hotspot_custom_topics
            WHERE username = ?
            ORDER BY created_at DESC
            """,
            (username,),
        )
        return [dict(row) for row in rows or []]

    @staticmethod
    def create(
        *,
        username: str,
        product_id: str,
        title: str,
        brief: str = "",
        hook: str = "",
        angle: str = "custom",
    ) -> Dict[str, Any]:
        topic_id = uuid.uuid4().hex[:16]
        now = _now_iso()
        payload = {
            "topic_id": topic_id,
            "username": username,
            "product_id": str(product_id),
            "title": title.strip(),
            "brief": brief.strip(),
            "hook": hook.strip(),
            "angle": angle or "custom",
            "created_at": now,
            "updated_at": now,
        }
        db_manager.insert("hotspot_custom_topics", payload)
        return payload

    @staticmethod
    def delete(topic_id: str, username: str) -> bool:
        db_manager.execute(
            "DELETE FROM hotspot_custom_topics WHERE topic_id = ? AND username = ?",
            (topic_id, username),
        )
        return True


def list_hotspot_products(username: str) -> List[Dict[str, str]]:
    comments = get_user_comments_data(username) or []
    metrics = get_user_metrics_data(username) or []
    product_ids: List[str] = []
    for row in list(comments) + list(metrics):
        pid = record_product(row)
        if pid and pid not in product_ids:
            product_ids.append(pid)
    if not product_ids:
        product_ids = ["730", "570"]
    product_ids.sort(key=lambda pid: len(_comments_for_product(comments, pid)), reverse=True)
    name_map = build_product_name_map(product_ids, username=username)
    return [
        {"product_id": pid, "product_name": _product_label(pid, name_map)}
        for pid in product_ids
    ]


def _custom_topic_card(row: Dict[str, Any], username: str) -> Dict[str, Any]:
    name_map = build_product_name_map([row["product_id"]], username=username)
    product_name = _product_label(row["product_id"], name_map)
    comments = get_user_comments_data(username) or []
    sample = len(_comments_for_product(comments, row["product_id"]))
    return {
        "id": f"custom:{row['topic_id']}",
        "topic_id": row["topic_id"],
        "product_id": row["product_id"],
        "product_name": product_name,
        "angle": row.get("angle") or "custom",
        "title": row["title"],
        "hook": row.get("hook") or "",
        "brief": row.get("brief") or "",
        "sample_size": sample,
        "source": "custom",
        "priority": 1000,
        "data_basis": resolve_user_data_source(username),
    }


def _infer_angle_from_brief(brief: str) -> str:
    text = brief.lower()
    if any(k in brief for k in ("流水", "收入", "营收", "暴跌", "下滑")):
        return "revenue_decline"
    if any(k in brief for k in ("口碑", "差评", "好评率", "舆论")):
        return "sentiment_crash"
    if any(k in brief for k in ("更新", "补丁", "版本", "patch")):
        return "patch_backlash"
    if any(k in brief for k in ("氪金", "付费", "通行证", "抽卡", "商业化")):
        return "monetization_backlash"
    if any(k in brief for k in ("留存", "流失", "新手", "匹配")):
        return "retention_risk"
    if any(k in text for k in ("revenue", "monetization", "retention", "patch")):
        return "patch_backlash"
    return "custom"


def _rule_suggest_topic(
    *,
    brief: str,
    product_id: str,
    product_name: str,
    sample_label: str,
) -> Dict[str, str]:
    brief = brief.strip()
    angle = _infer_angle_from_brief(brief)
    if angle != "custom":
        tpl = next((t for t in _TOPIC_TEMPLATES if t["angle"] == angle), None)
        if tpl:
            title = tpl["title_tpl"].format(name=product_name, sample=sample_label)
            hook = tpl["hook"]
            if brief and brief not in title:
                hook = brief[:120]
            return {"title": title, "hook": hook, "angle": angle}

    core = brief[:48] + ("…" if len(brief) > 48 else "")
    title = f"《{product_name}》{core}？基于 {sample_label} 条玩家评论的数据起底"
    return {
        "title": title,
        "hook": brief[:160] or f"围绕《{product_name}》的自定义热点问题展开数据复盘",
        "angle": "custom",
    }


async def suggest_hotspot_topic(
    username: str,
    *,
    brief: str,
    product_id: str,
) -> Dict[str, Any]:
    brief = (brief or "").strip()
    product_id = str(product_id or "").strip()
    if not brief:
        return {"success": False, "message": "请描述你想分析的热点问题"}
    if not product_id:
        return {"success": False, "message": "请选择产品"}

    facts = build_article_fact_pack(username, product_id)
    product_name = facts.get("product_name") or product_id
    sample_label = facts.get("sample_label") or "样本"
    fallback = _rule_suggest_topic(
        brief=brief,
        product_id=product_id,
        product_name=product_name,
        sample_label=sample_label,
    )
    using_llm = False
    llm_error = None

    if llm_is_configured():
        prompt = (
            "你是游戏行业选题编辑。根据用户描述的热点问题与产品事实，生成吸引人的深度分析标题与导语。\n"
            "要求：\n"
            "1. 标题参考「为什么《XX》…？基于 N 条玩家评论的数据起底」风格，但不要捏造未给出的收入数字。\n"
            "2. hook 为 1-2 句分析切入点。\n"
            "3. angle 从 revenue_decline|sentiment_crash|patch_backlash|monetization_backlash|retention_risk|custom 中选最贴切的一个。\n"
            "4. 只输出 JSON："
            '{"title":"...","hook":"...","angle":"..."}\n\n'
            f"用户问题：{brief}\n"
            f"产品：{product_name}（样本 {sample_label} 条）\n"
            f"事实摘要：{json.dumps({'sentiment': facts.get('sentiment'), 'themes': facts.get('theme_counts')}, ensure_ascii=False)}"
        )
        try:
            raw = await complete_prompt_with_retry(prompt, max_tokens=600, retries=1)
            parsed = parse_json_from_llm(raw)
            if isinstance(parsed, dict) and parsed.get("title"):
                fallback = {
                    "title": clean_llm_report_text(str(parsed["title"])),
                    "hook": clean_llm_report_text(str(parsed.get("hook") or "")),
                    "angle": str(parsed.get("angle") or fallback["angle"]),
                }
                using_llm = True
            else:
                llm_error = "AI 输出解析失败，已使用规则建议"
        except Exception as exc:
            llm_error = str(exc)

    return {
        "success": True,
        "title": fallback["title"],
        "hook": fallback["hook"],
        "angle": fallback["angle"],
        "brief": brief,
        "product_id": product_id,
        "product_name": product_name,
        "using_llm": using_llm,
        "llm_error": llm_error,
    }


def create_custom_hotspot_topic(
    username: str,
    *,
    product_id: str,
    title: str,
    brief: str = "",
    hook: str = "",
    angle: str = "custom",
) -> Dict[str, Any]:
    title = (title or "").strip()
    product_id = str(product_id or "").strip()
    if not product_id:
        return {"success": False, "message": "请选择产品"}
    if not title:
        return {"success": False, "message": "请填写标题"}
    row = HotspotCustomTopicRepository.create(
        username=username,
        product_id=product_id,
        title=title,
        brief=(brief or title).strip(),
        hook=hook.strip(),
        angle=angle or "custom",
    )
    return {"success": True, "topic": _custom_topic_card(row, username)}


def delete_custom_hotspot_topic(username: str, topic_id: str) -> Dict[str, Any]:
    topic_id = (topic_id or "").strip()
    if not topic_id:
        return {"success": False, "message": "topic_id 必填"}
    HotspotCustomTopicRepository.delete(topic_id, username)
    return {"success": True}


def _scale_sample_label(count: int) -> str:
    if count >= 10_000:
        return f"{count // 10_000}万"
    if count >= 1_000:
        return f"{count:,}"
    return str(max(count, 0))


def _theme_counts(comments: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    counter: Counter[str] = Counter()
    for row in comments:
        text = _comment_text(row).lower()
        if not text:
            continue
        for theme, keys in _THEME_KEYWORDS.items():
            if any(k.lower() in text for k in keys):
                counter[theme] += 1
    return [{"theme": k, "count": v} for k, v in counter.most_common(6)]


def _sample_quotes(comments: Sequence[Dict[str, Any]], *, limit: int = 5) -> List[str]:
    quotes: List[str] = []
    for row in comments:
        text = _comment_text(row)
        if len(text) < 12:
            continue
        mood = "正面" if _is_positive_comment(row) else "负面"
        quotes.append(f"[{mood}] {text[:180]}")
        if len(quotes) >= limit:
            break
    return quotes


def _metrics_highlights(metrics: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for row in metrics[:12]:
        metric = str(row.get("metric") or row.get("指标") or "").strip()
        value = row.get("值") if row.get("值") is not None else row.get("value")
        if metric and value not in (None, ""):
            rows.append({"metric": metric, "value": value})
    return rows


def _fetch_web_context(product_id: str) -> List[Dict[str, str]]:
    """Public web signals available in-app (Steam news API)."""
    if not str(product_id).isdigit():
        return []
    try:
        from src.services.steam_news import fetch_steam_news_items

        items = fetch_steam_news_items(product_id, count=5)
        return [
            {
                "title": row.get("version_label") or row.get("change_summary", "")[:80],
                "date": row.get("released_at") or "",
                "summary": (row.get("change_summary") or "")[:240],
                "type": row.get("change_type") or "",
            }
            for row in items
        ]
    except Exception:
        return []


def _sentiment_breakdown(comments: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    total = len(comments)
    if not total:
        return {"total": 0, "positive": 0, "negative": 0, "positive_rate": None}
    positive = sum(1 for row in comments if _is_positive_comment(row))
    negative = total - positive
    return {
        "total": total,
        "positive": positive,
        "negative": negative,
        "positive_rate": round(positive / total * 100, 1),
    }


def build_article_fact_pack(
    username: str,
    product_id: str,
    *,
    angle: str = "revenue_decline",
    custom_brief: Optional[str] = None,
) -> Dict[str, Any]:
    comments = get_user_comments_data(username) or []
    metrics = get_user_metrics_data(username) or []
    scoped_comments = _comments_for_product(comments, product_id)
    scoped_metrics = [m for m in metrics if product_matches(m, product_id)]
    name_map = build_product_name_map([product_id], username=username)
    product_name = _product_label(product_id, name_map)
    sentiment = _sentiment_breakdown(scoped_comments)
    sample_size = sentiment["total"] or len(scoped_comments)

    mvp_analysis = get_mvp_analysis() or {}
    product_report = None
    for report in mvp_analysis.get("product_reports") or []:
        if isinstance(report, dict) and product_matches(report, product_id):
            product_report = report
            break

    pack = {
        "product_id": product_id,
        "product_name": product_name,
        "angle": angle,
        "data_basis": resolve_user_data_source(username),
        "sample_size": sample_size,
        "sample_label": _scale_sample_label(sample_size),
        "sentiment": sentiment,
        "theme_counts": _theme_counts(scoped_comments),
        "sample_quotes": _sample_quotes(scoped_comments),
        "metrics_highlights": _metrics_highlights(scoped_metrics),
        "web_context": _fetch_web_context(product_id),
        "mvp_signals": {
            "top_issues": (product_report or {}).get("top_issues") or [],
            "strengths": (product_report or {}).get("strengths") or [],
        },
        "generated_at": datetime.now().isoformat(),
    }
    if custom_brief:
        pack["custom_brief"] = custom_brief.strip()
    return pack


def _angle_priority(angle: str, scoped_comments: Sequence[Dict[str, Any]]) -> int:
    """Rank topic angles by how well comment signals match the narrative."""
    sentiment = _sentiment_breakdown(scoped_comments)
    pos_rate = sentiment.get("positive_rate")
    theme_map = {row["theme"]: row["count"] for row in _theme_counts(scoped_comments)}
    score = 0
    if angle == "revenue_decline":
        if pos_rate is not None and pos_rate < 55:
            score += 20
        score += theme_map.get("内容更新", 0) // 5
    elif angle == "sentiment_crash":
        if pos_rate is not None and pos_rate < 50:
            score += 22
        score += sentiment.get("negative", 0) // 20
    elif angle == "patch_backlash":
        score += theme_map.get("内容更新", 0) // 3
        score += theme_map.get("平衡性", 0) // 4
    elif angle == "monetization_backlash":
        score += theme_map.get("商业化", 0) // 2
    elif angle == "retention_risk":
        score += theme_map.get("新手体验", 0) // 2
        score += theme_map.get("匹配/外挂", 0) // 3
        score += theme_map.get("性能体验", 0) // 4
    return score + min(len(scoped_comments) // 50, 10)


def discover_hotspot_topics(username: str, *, limit: int = 12) -> List[Dict[str, Any]]:
    custom_cards = [
        _custom_topic_card(row, username)
        for row in HotspotCustomTopicRepository.list_for_user(username)
    ]
    auto_limit = max(0, limit - len(custom_cards))

    comments = get_user_comments_data(username) or []
    metrics = get_user_metrics_data(username) or []
    name_map = build_product_name_map(username=username)

    product_ids: List[str] = []
    for row in list(comments) + list(metrics):
        pid = record_product(row)
        if pid and pid not in product_ids:
            product_ids.append(pid)

    if not product_ids:
        for preset in ("730", "570"):
            product_ids.append(preset)

    product_ids.sort(
        key=lambda pid: len(_comments_for_product(comments, pid)),
        reverse=True,
    )

    topics: List[Dict[str, Any]] = []
    for pid in product_ids[:6]:
        scoped = _comments_for_product(comments, pid)
        sample = len(scoped)
        name = _product_label(pid, name_map)
        label = _scale_sample_label(sample) if sample else "样本"
        templates = sorted(
            _TOPIC_TEMPLATES,
            key=lambda tpl: _angle_priority(tpl["angle"], scoped),
            reverse=True,
        )
        for tpl in templates:
            topics.append(
                {
                    "id": f"{pid}:{tpl['angle']}",
                    "product_id": pid,
                    "product_name": name,
                    "angle": tpl["angle"],
                    "title": tpl["title_tpl"].format(name=name, sample=label),
                    "hook": tpl["hook"],
                    "sample_size": sample,
                    "priority": _angle_priority(tpl["angle"], scoped),
                    "source": "auto",
                    "data_basis": resolve_user_data_source(username),
                }
            )

    topics.sort(key=lambda row: (row.get("priority", 0), row.get("sample_size", 0)), reverse=True)
    return custom_cards + topics[:auto_limit]


def _rule_article_markdown(facts: Dict[str, Any]) -> str:
    name = facts.get("product_name") or facts.get("product_id")
    sample = facts.get("sample_label") or facts.get("sample_size") or 0
    sentiment = facts.get("sentiment") or {}
    pos_rate = sentiment.get("positive_rate")
    themes = facts.get("theme_counts") or []
    quotes = facts.get("sample_quotes") or []
    web = facts.get("web_context") or []
    basis = facts.get("data_basis") or "unknown"

    title_angle = {
        "revenue_decline": f"为什么《{name}》新版本流水暴跌？基于 {sample} 条玩家评论的数据起底",
        "sentiment_crash": f"《{name}》口碑滑坡背后：{sample} 条真实玩家在说什么",
        "patch_backlash": f"一次更新引发的增长危机：《{name}》全网评论复盘",
        "monetization_backlash": f"氪金争议如何拖累《{name}》？评论样本里的商业化信号",
        "retention_risk": f"《{name}》留存告急？从评论样本看流失前兆",
        "custom": facts.get("custom_brief") or f"《{name}》行业热点深度复盘",
    }.get(facts.get("angle"), f"《{name}》行业热点深度复盘")

    custom_brief = (facts.get("custom_brief") or "").strip()
    lines = [
        f"# {title_angle}",
        "",
        f"> 数据说明：本文基于平台内已抓取/导入评论与公开 Steam 新闻信号生成（来源：`{basis}`）。"
        f" 样本量 **{sentiment.get('total', 0)}** 条，非全网全量统计。",
        "",
        "## 一、热点背景",
        "",
    ]
    if custom_brief:
        lines.append(f"**自定义分析焦点**：{custom_brief}")
        lines.append("")
    lines.extend([
        f"围绕《{name}》，近期社区讨论集中在版本体验、商业化与匹配质量等议题。"
        " 以下分析将评论情绪结构与主题频次对齐，帮助判断舆情是否可能向收入与留存传导。",
        "",
        "## 二、玩家情绪光谱",
        "",
    ])
    if pos_rate is not None:
        lines.append(
            f"- 样本好评率约 **{pos_rate}%**（正面 {sentiment.get('positive', 0)} / "
            f"负面 {sentiment.get('negative', 0)}）"
        )
    else:
        lines.append("- 当前样本不足以计算情绪占比，建议先在 /mvp 抓取或导入评论。")

    if themes:
        lines.extend(["", "### 高频吐槽主题", ""])
        for item in themes:
            lines.append(f"- **{item['theme']}**：{item['count']} 条相关评论")
    else:
        lines.extend(["", "暂未识别出明显主题簇，可扩大抓取窗口或合并多平台样本。", ""])

    if web:
        lines.extend(["", "## 三、版本与公开舆情线索", ""])
        for item in web[:3]:
            date = f"（{item['date']}）" if item.get("date") else ""
            lines.append(f"- {item.get('title', '更新')}{date}：{item.get('summary', '')[:120]}")

    if quotes:
        lines.extend(["", "## 四、玩家原声摘录", ""])
        for q in quotes:
            lines.append(f"- {q}")

    lines.extend(
        [
            "",
            "## 五、对流水与留存的启示（规则引擎初稿）",
            "",
            "1. 若负面主题集中在「平衡性/匹配/性能」，优先排查版本回归与服务器质量，再评估商业化节奏。",
            "2. 若「商业化」主题抬升且好评率下滑，建议拆分付费点贡献与免费体验受损路径。",
            "3. 将本文结论与看板 KPI、复盘归档对照，设置 1–2 周可验证的实验指标。",
        ]
    )
    return "\n".join(lines)


def _strip_md_fences(text: str) -> str:
    t = (text or "").strip()
    if not t:
        return ""
    t = re.sub(r"^```(?:markdown|md|json)?\s*\n?", "", t, flags=re.IGNORECASE)
    t = re.sub(r"\n?```\s*$", "", t)
    return t.strip()


def _compact_fact_pack_for_llm(facts: Dict[str, Any]) -> Dict[str, Any]:
    compact = {
        "product_id": facts.get("product_id"),
        "product_name": facts.get("product_name"),
        "angle": facts.get("angle"),
        "sample_size": facts.get("sample_size"),
        "sample_label": facts.get("sample_label"),
        "data_basis": facts.get("data_basis"),
        "sentiment": facts.get("sentiment"),
        "theme_counts": facts.get("theme_counts"),
        "metrics_highlights": (facts.get("metrics_highlights") or [])[:8],
        "web_context": (facts.get("web_context") or [])[:3],
        "mvp_signals": facts.get("mvp_signals"),
        "sample_quotes": (facts.get("sample_quotes") or [])[:3],
    }
    if facts.get("custom_brief"):
        compact["custom_brief"] = facts["custom_brief"]
    return compact


def _article_footer(
    *,
    using_llm: bool,
    llm_configured: bool,
    llm_error: Optional[str],
    generated_at: str,
    llm_provider: Optional[str] = None,
) -> str:
    if using_llm:
        provider = f" · {llm_provider}" if llm_provider else ""
        return f"\n---\n*生成时间：{generated_at} · AI 撰写{provider}*"
    if llm_configured and llm_error:
        return f"\n---\n*生成时间：{generated_at} · 规则引擎回退（{llm_error}）*"
    if llm_configured:
        return f"\n---\n*生成时间：{generated_at} · 规则引擎回退*"
    return f"\n---\n*生成时间：{generated_at} · 规则引擎（未配置 LLM）*"


def _decode_json_string_fragment(raw: str) -> str:
    wrapped = f'"{raw}"'
    try:
        return json.loads(wrapped)
    except json.JSONDecodeError:
        return raw.replace('\\"', '"').replace("\\n", "\n").replace("\\t", "\t")


def _looks_like_json_wrapper(text: str) -> bool:
    t = (text or "").strip()
    return t.startswith("{") and ('"markdown"' in t or '"title"' in t or '"summary"' in t)


def _normalize_article_text(text: str) -> str:
    return _strip_md_fences(str(text or "").strip())


def _extract_partial_llm_article(raw: str) -> Optional[Dict[str, Any]]:
    """Best-effort parse when json.loads fails on long markdown payloads."""
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end <= start:
        return None
    snippet = raw[start : end + 1]

    def grab(field: str) -> str:
        match = re.search(
            rf'"{field}"\s*:\s*"((?:[^"\\]|\\.)*)"',
            snippet,
            flags=re.DOTALL,
        )
        return _decode_json_string_fragment(match.group(1)) if match else ""

    title = grab("title")
    summary = grab("summary")
    markdown = grab("markdown") or grab("body")
    if not markdown:
        return None
    markdown = _strip_md_fences(markdown)
    if "\\n" in markdown and markdown.count("\n") < 3:
        markdown = markdown.replace("\\n", "\n").replace("\\t", "\t").replace('\\"', '"')
    return {
        "title": _normalize_article_text(title),
        "summary": _normalize_article_text(summary),
        "markdown": markdown.strip(),
    }


def _normalize_article_markdown(text: str) -> str:
    md = _strip_md_fences(str(text or "").strip())
    if not md:
        return ""
    if _looks_like_json_wrapper(md):
        partial = _extract_partial_llm_article(md)
        return partial.get("markdown", "") if partial else ""
    if "\\n" in md and md.count("\n") < 3:
        md = md.replace("\\n", "\n").replace("\\t", "\t").replace('\\"', '"')
    return md.strip()


def _parse_llm_article(raw: str, facts: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    raw = (raw or "").strip()
    if not raw:
        return None

    parsed = parse_json_from_llm(raw)
    if not isinstance(parsed, dict):
        parsed = _extract_partial_llm_article(raw)

    if isinstance(parsed, dict):
        title = _normalize_article_text(parsed.get("title") or "")
        summary = _normalize_article_text(parsed.get("summary") or "")
        markdown = _normalize_article_markdown(parsed.get("markdown") or parsed.get("body") or "")
        if markdown and not _looks_like_json_wrapper(markdown):
            if summary and summary not in markdown:
                markdown = f"> {summary}\n\n{markdown}"
            return {"title": title, "summary": summary, "markdown": markdown}

    if _looks_like_json_wrapper(raw):
        return None

    text = _normalize_article_markdown(clean_llm_report_text(raw))
    if text and len(text) > 200 and (
        text.startswith("#") or re.search(r"^##\s", text, re.MULTILINE)
    ):
        title_match = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
        title = title_match.group(1).strip() if title_match else ""
        return {"title": title, "summary": "", "markdown": text}
    return None


async def generate_hotspot_article(
    username: str,
    *,
    product_id: str,
    angle: str = "revenue_decline",
    custom_title: Optional[str] = None,
    custom_brief: Optional[str] = None,
) -> Dict[str, Any]:
    product_id = str(product_id or "").strip()
    if not product_id:
        return {"success": False, "message": "请选择产品"}

    brief = (custom_brief or "").strip() or None
    facts = build_article_fact_pack(username, product_id, angle=angle, custom_brief=brief)
    name_map = build_product_name_map([product_id], username=username)
    product_name = _product_label(product_id, name_map)

    default_title = next(
        (
            t["title_tpl"].format(name=product_name, sample=facts.get("sample_label") or "样本")
            for t in _TOPIC_TEMPLATES
            if t["angle"] == angle
        ),
        (brief[:60] + "…") if brief and len(brief) > 60 else (brief or f"《{product_name}》行业热点深度分析"),
    )
    title = (custom_title or "").strip() or default_title

    using_llm = False
    llm_error = None
    llm_configured = llm_is_configured()
    generated_at = datetime.now().isoformat()
    markdown = _rule_article_markdown({**facts, "product_name": product_name})

    if llm_configured:
        custom_focus = ""
        if brief:
            custom_focus = f"\n用户自定义分析焦点：{brief}\n请全文围绕该问题组织论证，并在「热点背景」中复述该焦点。\n"
        prompt = (
            "你是资深游戏行业数据记者，擅长写「热点起底」式深度分析长文。\n"
            "根据下列事实 JSON（评论样本统计、主题、公开新闻、指标摘要）撰写文章。\n"
            "要求：\n"
            "1. 标题吸引人，可参考 fact_pack 中的 angle 与样本量，但不要捏造未给出的精确收入数字。\n"
            "2. 明确标注数据为「平台内评论样本 + 公开新闻」，不可写成已验证的全网 20 万条除非 sample_size 接近。\n"
            "3. 结构含：热点背景、数据样本说明、情绪与主题、版本/舆情关联、对流水/留存的影响推演、运营建议。\n"
            "4. 引用 1-3 条 sample_quotes 时要保留 [正面]/[负面] 标注。\n"
            "5. 只输出 JSON，不要用 Markdown 代码块包裹："
            '{"title":"...","summary":"80-120字导语","markdown":"完整 Markdown 正文（含 ## 小节）"}\n'
            f"{custom_focus}\n"
            f"{json.dumps(_compact_fact_pack_for_llm(facts), ensure_ascii=False)}"
        )
        try:
            raw = await complete_prompt_with_retry(
                prompt,
                max_tokens=min(int(LLM_CONFIG.get("max_tokens") or 2800), 2800),
                timeout=120,
                retries=1,
            )
            parsed = _parse_llm_article(raw, facts)
            if parsed and parsed.get("markdown"):
                markdown = parsed["markdown"]
                title = parsed.get("title") or title
                using_llm = True
            else:
                llm_error = "LLM 输出解析失败（请检查模型是否支持长 JSON 输出）"
        except Exception as exc:
            llm_error = str(exc)

    footer = _article_footer(
        using_llm=using_llm,
        llm_configured=llm_configured,
        llm_error=llm_error,
        generated_at=generated_at,
        llm_provider=_provider_label() if using_llm else None,
    )
    if footer.strip() not in markdown:
        markdown = markdown.rstrip() + footer

    return {
        "success": True,
        "title": title,
        "summary": _extract_summary(markdown),
        "markdown": markdown,
        "html": _markdown_to_html(markdown),
        "facts": facts,
        "product_id": product_id,
        "product_name": product_name,
        "angle": angle,
        "using_llm": using_llm,
        "llm_provider": _provider_label() if using_llm else None,
        "llm_model": LLM_CONFIG.get("model") if using_llm else None,
        "llm_error": llm_error,
        "llm_configured": llm_configured,
        "generated_at": generated_at,
    }


def _extract_summary(markdown: str) -> str:
    for line in markdown.splitlines():
        text = line.strip()
        if text.startswith(">"):
            return text.lstrip("> ").strip()
        if text and not text.startswith("#"):
            return text[:200]
    return ""


def _markdown_to_html(markdown: str) -> str:
    lines = markdown.splitlines()
    out: List[str] = ['<article class="hotspot-article">']
    in_ul = False

    def close_ul() -> None:
        nonlocal in_ul
        if in_ul:
            out.append("</ul>")
            in_ul = False

    def esc(s: str) -> str:
        return (
            s.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

    for raw in lines:
        line = raw.rstrip()
        if not line.strip():
            close_ul()
            continue
        if line.startswith("### "):
            close_ul()
            out.append(f"<h4>{esc(line[4:])}</h4>")
        elif line.startswith("## "):
            close_ul()
            out.append(f"<h3>{esc(line[3:])}</h3>")
        elif line.startswith("# "):
            close_ul()
            out.append(f"<h2>{esc(line[2:])}</h2>")
        elif line.startswith("> "):
            close_ul()
            out.append(f'<blockquote class="lead">{esc(line[2:])}</blockquote>')
        elif line.startswith("- "):
            if not in_ul:
                out.append("<ul>")
                in_ul = True
            out.append(f"<li>{esc(line[2:])}</li>")
        else:
            close_ul()
            out.append(f"<p>{esc(line)}</p>")
    close_ul()
    out.append("</article>")
    return "".join(out)

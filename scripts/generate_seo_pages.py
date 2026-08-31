#!/usr/bin/env python3
"""生成「游戏舆情 AI 分析平台」SEO 页面(基于离线原型的信息架构)。

产出: src/templates/seo/*.html
- 1 主题首页 + 1 核心产品页 + 5 内容支撑页
- 每页含 title/description/keywords/canonical、数据边界标注、站内互链、CTA
"""

from __future__ import annotations

import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "src" / "templates" / "seo"
BASE_URL = "https://game-analyzer-eq8i.onrender.com"

STYLE = """<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', sans-serif; background: #0f1419; color: #e7ecf3; line-height: 1.7; }
.topbar { position: sticky; top: 0; z-index: 100; display: flex; flex-wrap: wrap; gap: 4px 14px; align-items: center; padding: 10px 24px; background: rgba(15,20,25,.92); backdrop-filter: blur(10px); border-bottom: 1px solid rgba(255,255,255,.08); font-size: .85rem; }
.topbar a { color: #94a3b8; text-decoration: none; }
.topbar a:hover { color: #67e8f9; }
.topbar .brand { font-weight: 700; color: #e7ecf3; margin-right: 8px; }
.wrap { max-width: 1080px; margin: 0 auto; padding: 56px 24px 48px; }
.hero { text-align: center; margin-bottom: 40px; }
.hero h1 { font-size: 2.1rem; letter-spacing: -0.02em; margin-bottom: 12px; }
.hero .sub { color: #94a3b8; max-width: 760px; margin: 0 auto 20px; font-size: 1.02rem; }
.badges { display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; margin-bottom: 24px; }
.badge { padding: 4px 12px; border-radius: 999px; font-size: .78rem; }
.badge.real { background: rgba(16,185,129,.15); color: #6ee7b7; border: 1px solid rgba(16,185,129,.35); }
.badge.demo { background: rgba(245,158,11,.15); color: #fcd34d; border: 1px solid rgba(245,158,11,.35); }
.badge.keyword { background: rgba(56,189,248,.12); color: #7dd3fc; border: 1px solid rgba(56,189,248,.3); }
.cta { display: flex; flex-wrap: wrap; gap: 12px; justify-content: center; }
.btn { padding: 12px 24px; border-radius: 12px; font-weight: 600; text-decoration: none; display: inline-block; }
.btn-primary { background: linear-gradient(135deg,#06b6d4,#0891b2); color: #fff; }
.btn-ghost { background: rgba(255,255,255,.08); color: #e7ecf3; border: 1px solid rgba(255,255,255,.15); }
.btn-demo { background: linear-gradient(135deg,#8b5cf6,#6d28d9); color: #fff; }
.grid { display: grid; grid-template-columns: repeat(auto-fit,minmax(280px,1fr)); gap: 16px; margin: 28px 0; }
.card { background: rgba(255,255,255,.05); border: 1px solid rgba(255,255,255,.09); border-radius: 14px; padding: 20px; }
.card h3 { color: #06b6d4; font-size: 1rem; margin-bottom: 10px; }
.card p, .card li { color: #94a3b8; font-size: .88rem; }
.card ul { padding-left: 18px; }
.section-title { font-size: 1.15rem; color: #c4b5fd; margin: 28px 0 8px; }
.boundary { margin: 28px 0; padding: 18px; border-radius: 12px; background: rgba(245,158,11,.08); border: 1px solid rgba(245,158,11,.25); font-size: .85rem; }
.boundary h3 { color: #fcd34d; margin-bottom: 10px; font-size: .95rem; }
.boundary ul { color: #d6d3d1; padding-left: 18px; }
.boundary .ok { color: #6ee7b7; }
.boundary .warn { color: #fcd34d; }
.xlinks { display: flex; flex-wrap: wrap; gap: 10px; margin: 24px 0; }
.xlinks a { color: #7dd3fc; text-decoration: none; font-size: .88rem; border: 1px solid rgba(125,211,252,.3); padding: 6px 12px; border-radius: 8px; }
.xlinks a:hover { background: rgba(125,211,252,.1); }
.footer { text-align: center; color: #64748b; font-size: .78rem; padding: 28px 16px 40px; border-top: 1px solid rgba(255,255,255,.06); }
.footer a { color: #94a3b8; text-decoration: none; margin: 0 6px; }
.flow { margin: 28px 0; padding: 18px; border-radius: 12px; background: rgba(255,255,255,.04); border: 1px solid rgba(255,255,255,.08); }
.flow h3 { color: #c4b5fd; margin-bottom: 10px; font-size: .95rem; }
.flow ol { color: #94a3b8; font-size: .88rem; padding-left: 20px; }
.sysnote { margin: 0 auto 28px; max-width: 900px; padding: 14px 18px; border-radius: 12px; background: rgba(56,189,248,.08); border: 1px solid rgba(56,189,248,.3); font-size: .85rem; color: #d6d3d1; text-align: left; }
.sysnote strong { color: #7dd3fc; }
.sysnote .sys-a { color: #a5b4fc; }
.sysnote .sys-b { color: #6ee7b7; }
</style>"""

NAV_ITEMS = [
    ("平台首页", "/game-public-opinion-ai-analysis"),
    ("AI 监测系统", "/ai-game-opinion-monitoring-system"),
]
HUB_LINKS = [
    ("负面风险识别", "/game-negative-public-opinion-monitoring"),
    ("玩家体验分析", "/mobile-game-player-experience-analysis"),
    ("热点事件追踪", "/game-hot-event-tracking"),
    ("商业化争议", "/game-monetization-controversy-monitoring"),
    ("跨平台聚合", "/cross-platform-game-opinion-aggregation"),
]

ALL_PAGES = {
    "/game-public-opinion-ai-analysis": "主题首页",
    "/ai-game-opinion-monitoring-system": "AI 监测系统",
    "/game-negative-public-opinion-monitoring": "负面风险",
    "/mobile-game-player-experience-analysis": "玩家体验",
    "/game-hot-event-tracking": "热点追踪",
    "/game-monetization-controversy-monitoring": "商业化争议",
    "/cross-platform-game-opinion-aggregation": "跨平台预警",
}


def _next_steps(page: dict) -> str:
    """因果路径: 信息查询 -> 上级(主题首页/产品页) -> 行动(体验/看板/试用)。"""
    steps = page.get("next_steps") or []
    cards = "".join(
        f"""<div class="card"><h3 style="color:#8b5cf6;">{i + 1}. {step["title"]}</h3>
<p>{step.get("desc","")}</p>
<p style="margin-top:8px;"><a href="{step["href"]}" style="color:#7dd3fc;font-size:.85rem;">前往 →</a></p></div>"""
        for i, step in enumerate(steps)
    )
    return f'<h2 class="section-title">下一步 · 推荐路径</h2><div class="grid">{cards}</div>'


def render(page: dict) -> str:
    url = page["url"]
    x = _next_steps(page)
    cards = "".join(
        f"""<div class="card"><h3>{sec["title"]}</h3><p>{sec.get("text","")}</p>"""
        + ("<ul>" + "".join(f"<li>{li}</li>" for li in sec["list"]) + "</ul>" if sec.get("list") else "")
        + "</div>"
        for sec in page["sections"]
    )
    boundary_title = page.get('boundary_title') or page['h1']
    boundary = f"""<div class="boundary"><h3>⚠ 数据边界 · {boundary_title}</h3>
<ul>
<li class="ok">✅ 可由公开数据计算：{page["real"]}</li>
<li class="warn">⚠ 需工具核验 / 待业务数据：{page["pending"]}</li>
<li>不编造内容：未完成工具核验的数据不作为业务结论（详见 <a href="/trust" style="color:#7dd3fc;">数据与订阅说明</a>）。</li>
</ul></div>"""
    hub = ""
    if url in [href for _, href in NAV_ITEMS]:
        hub_cards = "".join(
            f'<div class="card"><h3>{name}</h3><p><a href="{href}" style="color:#7dd3fc;font-size:.85rem;">了解详情 →</a></p></div>'
            for name, href in HUB_LINKS
        )
        hub = f'<h2 class="section-title">5 大能力场景</h2><div class="grid">{hub_cards}</div>'

    flow = ""
    if page.get("flow"):
        flow = f'<div class="flow"><h3>{page["flow"]["title"]}</h3><ol>' + "".join(f"<li>{li}</li>" for li in page["flow"]["list"]) + "</ol></div>"

    nav = "".join(
        f'<a href="{href}" class="active" style="color:#67e8f9;">{name}</a>' if href == url else f'<a href="{href}">{name}</a>'
        for name, href in NAV_ITEMS
    )
    if url not in [href for _, href in NAV_ITEMS]:
        nav += '<span style="color:#64748b;font-size:.8rem;"> · 内容支撑页</span>' 

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{page["title"]}</title>
<meta name="description" content="{page["description"]}">
<meta name="keywords" content="{page["keywords"]}">
<link rel="canonical" href="{BASE_URL}{url}">
<meta property="og:title" content="{page["title"]}">
<meta property="og:description" content="{page["description"]}">
<meta property="og:type" content="website">
<script type="application/ld+json">{{"@context":"https://schema.org","@type":"WebPage","name":"{page["title"]}","url":"{BASE_URL}{url}","description":"{page["description"]}"}}</script>
{STYLE}
</head>
<body>
<header class="topbar"><span class="brand">🎮 游戏舆情 AI 分析</span>{nav}<a href="/dashboard" style="margin-left:auto;color:#86efac;">进入看板 →</a></header>
<main class="wrap">
  <div class="sysnote">
    <strong>两系统定位</strong>：本页属于 <span class="sys-a">「游戏舆情 AI 分析平台」内容站</span> —— 对外能力介绍与行业科普（不含实时数据）。
    实际的抓取、分析与看板在 <span class="sys-b">「Game Analyzer 数据分析工具」</span> 中完成，<a href="/login?redirect=/dashboard" style="color:#7dd3fc;">登录后进入 →</a>
  </div>
  <section class="hero">
    <h1>{page["h1"]}</h1>
    <p class="sub">{page["sub"]}</p>
    <div class="badges">
      {''.join(f'<span class="badge {b["type"]}">{b["text"]}</span>' for b in page["badges"])}
    </div>
    <div class="cta">{page["cta"]}</div>
  </section>
  <h2 class="section-title">{page.get("section_heading","核心内容")}</h2>
  <div class="grid">{cards}</div>
  {flow}
  {hub}
  {boundary}
  {x}
  <div class="cta" style="margin-top:20px;">{page["cta"]}</div>
</main>
<footer class="footer">
  <div>游戏舆情 AI 分析 · <a href="/">产品首页</a> · <a href="/dashboard">运营看板</a> · <a href="/guide">分析向导</a> · <a href="/pricing">订阅</a> · <a href="/trust">数据边界</a> · <a href="/privacy">隐私</a></div>
  <div style="margin-top:8px;">基于公开评论数据（Steam / TapTap / Google Play）；经营类指标需接入业务数据后计算。</div>
</footer>
</body>
</html>"""


PAGES = [
    {
        "url": "/game-public-opinion-ai-analysis",
        "title": "游戏舆情 AI 分析平台 | AI 全域游戏舆情监控、风险识别与口碑分析",
        "description": "面向游戏运营与风控的 AI 游戏舆情分析平台：负面舆情监控、玩家口碑分析、热点事件追踪与跨平台聚合预警，基于公开评论数据，边界清晰。",
        "keywords": "游戏舆情分析,游戏口碑分析,AI 舆情监控,游戏负面舆情,游戏热点追踪,游戏舆情预警",
        "h1": "🎮 游戏舆情 AI 分析平台",
        "sub": "AI 全域游戏舆情监控、风险识别与口碑分析一体化：抓取 Steam / TapTap / Google Play 公开评论，语义聚类提炼主题，跨平台聚合预警，来源可回查。",
        "badges": [
            {"type": "real", "text": "公开评论真数据"},
            {"type": "keyword", "text": "主关键词：游戏舆情分析"},
            {"type": "demo", "text": "经营指标需业务数据核验"},
        ],
        "section_heading": "平台核心能力",
        "sections": [
            {"title": "负面舆情监控", "text": "负面评价、玩家投诉、BUG 反馈与集中扩散线索，聚类去重后保留代表样本与出处。"},
            {"title": "玩家口碑分析", "text": "情感与主题标签（性能/匹配/外挂/付费…）聚类，定位高频负面体验与版本反馈。"},
            {"title": "热点事件追踪", "text": "发现、升温、扩散、回落全周期记录，事件摘要与证据清单可回查。"},
            {"title": "跨平台聚合预警", "text": "统一保存来源平台、时间、原文与链接，按规则阈值 + AI 分类分级预警。"},
        ],
        "flow": {
            "title": "两系统关系（业务边界）",
            "list": [
                "系统 A「游戏舆情 AI 分析平台」：本内容站 —— 对外能力介绍、行业科普与 SEO 获客，不承载实时数据。",
                "系统 B「Game Analyzer 数据分析工具」：实际产品 —— 抓取公开评论、清洗打标、看板与报告，需登录使用。",
                "两者关系：内容站负责「讲清能力、引入用户」，数据工具负责「落地分析」，互不混用、单向引导。",
            ],
        },
        "real": "评论情感与主题聚类、负面/正面声量趋势（时间窗内评论数）、跨平台聚合（已接入平台）、热词与高频问题。",
        "pending": "真实声量与全平台覆盖率、DAU/留存/收入影响、转化漏斗、商业化争议对经营结果的影响。",
        "cta": '<a class="btn btn-demo" href="/login?redirect=/guide">🚀 进入数据工具（登录后分析）</a><a class="btn btn-primary" href="/pricing">申请试用</a><a class="btn btn-ghost" href="/ai-game-opinion-monitoring-system">了解 AI 监测系统</a>',
    },
    {
        "url": "/ai-game-opinion-monitoring-system",
        "title": "AI 游戏舆情监测系统 | 负面舆情抓取、智能识别、实时预警与跨平台聚合",
        "description": "专为游戏行业设计的 AI 全网舆情智能分析系统：负面舆情抓取、风险识别、实时预警与跨平台聚合，帮助运营、公关与策划快速掌握口碑变化。",
        "keywords": "AI 游戏舆情监测,游戏负面舆情识别,游戏舆情预警系统,游戏口碑监控,游戏舆情系统",
        "h1": "🤖 AI 游戏舆情监测系统",
        "sub": "专为游戏行业设计的 AI 全网舆情智能分析系统：负面舆情抓取、智能风险识别、实时预警与跨平台聚合，来源可回查、结论可核验。",
        "badges": [
            {"type": "real", "text": "公开数据驱动"},
            {"type": "keyword", "text": "主关键词：AI 游戏舆情监测系统"},
        ],
        "section_heading": "系统能力",
        "sections": [
            {"title": "负面舆情抓取", "text": "自动抓取商店公开评论与公开反馈，统一入库并保留来源、时间与原文 ID。"},
            {"title": "智能风险识别", "text": "语义聚类 + 规则阈值共同识别风险线索，输出代表样本与相似度依据。"},
            {"title": "实时预警", "text": "分级预警机制：由规则阈值与 AI 分类共同产生提示，具体规则可按业务确认。"},
            {"title": "跨平台聚合", "text": "Steam / TapTap / Google Play 等多平台聚合，时间与口径统一。"},
            {"title": "效率对比", "text": "对比人工检索：覆盖更广、响应更快、重复内容自动去重。"},
            {"title": "适用用户", "text": "游戏运营、公关风控、产品策划与行业分析师。"},
        ],
        "real": "评论抓取、情感/主题聚类、负面线索与代表样本、跨平台（已接入平台）聚合、预警阈值触发的提示。",
        "pending": "全平台（短视频/论坛）覆盖率、真实声量、预警分级规则与经营结果影响。",
        "cta": '<a class="btn btn-primary" href="/pricing">预约试用 / Demo 申请</a><a class="btn btn-ghost" href="/game-negative-public-opinion-monitoring">负面风险识别</a>',
    },
    {
        "url": "/game-negative-public-opinion-monitoring",
        "title": "游戏负面舆情风险识别 | Game negative public opinion monitoring",
        "description": "游戏负面舆情如何识别：负面评价、玩家投诉、BUG 反馈与集中扩散线索的 AI 识别逻辑（公开抓取、语义聚类、风险分类、代表样本与出处保留）。",
        "keywords": "Game negative public opinion monitoring,游戏负面舆情,游戏舆情风险识别,游戏差评分析,游戏 BUG 反馈监测",
        "h1": "⚠ 游戏负面舆情风险识别",
        "sub": "从公开评论中发现负面风险线索：负面评价、玩家投诉、BUG 反馈与集中扩散，AI 聚类去重后保留代表样本与出处。",
        "badges": [{"type": "keyword", "text": "主关键词：Game negative public opinion monitoring"}],
        "section_heading": "风险识别方法",
        "sections": [
            {"title": "核心风险场景", "text": "", "list": ["负面评价集中出现", "玩家投诉与退款诉求", "BUG / 闪退 / 卡顿反馈", "同一问题跨平台扩散"]},
            {"title": "传统风控痛点", "text": "", "list": ["人工检索覆盖有限", "响应滞后", "重复内容干扰判断", "缺少来源留痕"]},
            {"title": "AI 识别逻辑", "text": "", "list": ["公开内容抓取", "语义聚类去重", "风险分类与主题提炼", "代表样本与出处保留"]},
            {"title": "落地应用方法", "text": "AI 提示风险，运营人员核验来源、判断影响并选择处置动作；未核验不作为结论。"},
        ],
        "real": "负面评论识别、主题聚类（性能/外挂/平衡等）、负面声量趋势与代表样本。",
        "pending": "典型负面舆情处置案例、风控落地流程、真实影响量级。",
        "cta": '<a class="btn btn-demo" href="/login?redirect=/dashboard">进入数据工具 · 查看预警</a><a class="btn btn-ghost" href="/ai-game-opinion-monitoring-system">了解 AI 监测系统</a>',
    },
    {
        "url": "/mobile-game-player-experience-analysis",
        "title": "手游玩家体验舆情分析 | Mobile game bug public opinion feedback",
        "description": "手游玩家体验舆情分析：BUG、闪退、卡顿、掉线与服务器异常反馈的自动分析方法（公开抓取、语义去重、相似聚类、代表样本与标签归类）。",
        "keywords": "Mobile game bug public opinion feedback,Server lag public opinion discussion,手游 BUG 舆情,玩家体验分析,手游服务器延迟舆情",
        "h1": "📱 手游玩家体验舆情分析",
        "sub": "面向 BUG、闪退、卡顿、掉线与服务器异常等高频负面体验的舆情分析方法，把问题簇、声量口径与原文证据交给产品与运维核验。",
        "badges": [
            {"type": "keyword", "text": "主关键词：Mobile game bug public opinion feedback"},
            {"type": "keyword", "text": "支持：Server lag public opinion discussion"},
        ],
        "section_heading": "玩家体验分析方法",
        "sections": [
            {"title": "高频负面体验", "text": "", "list": ["BUG / 闪退", "卡顿 / 掉帧", "掉线 / 排队", "服务器异常 / 延迟"]},
            {"title": "运营影响", "text": "可能影响口碑、留存与版本评价；实际影响需业务数据核验。"},
            {"title": "自动分析方法", "text": "", "list": ["抓取公开反馈", "语义去重", "相似聚类", "代表样本选择", "标签归类"]},
            {"title": "版本优化思路", "text": "将问题簇、声量口径和原文证据交给产品及运维核验后排期修复。"},
        ],
        "real": "BUG/卡顿/掉线等主题聚类与代表样本、问题声量（时间窗内评论数）、按游戏/平台的分布。",
        "pending": "手游常见问题台账、优化落地案例、对留存与版本评价的实际影响。",
        "cta": '<a class="btn btn-demo" href="/login?redirect=/guide">进入数据工具 · 分析体验</a><a class="btn btn-ghost" href="/ai-game-opinion-monitoring-system">了解监测系统</a>',
    },
    {
        "url": "/game-hot-event-tracking",
        "title": "游戏热点事件追踪与复盘 | Online game hot event tracking",
        "description": "游戏热点事件如何全周期追踪与复盘：发现、升温、扩散、回落阶段保持来源与时间可回查，形成事件摘要、代表观点与证据清单。",
        "keywords": "Online game hot event tracking,Game trend public opinion report,游戏热点追踪,游戏舆情报告,游戏事件复盘",
        "h1": "⌁ 游戏热点事件追踪与复盘",
        "sub": "事件信息跨平台扩散，观点随时间和渠道变化；全周期追踪并保留来源与时间可回查，趋势结论需由工具数据计算。",
        "badges": [{"type": "keyword", "text": "主关键词：Online game hot event tracking"}],
        "section_heading": "事件追踪方法",
        "sections": [
            {"title": "传播特征", "text": "事件信息跨平台扩散，观点随时间、渠道与关键节点变化。"},
            {"title": "人工追踪短板", "text": "信息分散且更新频繁，容易漏掉关键转折与反向证据。"},
            {"title": "全周期追踪", "text": "发现、升温、扩散、回落与复盘阶段，保持来源与时间可回查。"},
            {"title": "趋势研判", "text": "趋势图展示结构；真实声量与增幅必须由工具数据计算，未核验不写结论。"},
            {"title": "报告产出", "text": "", "list": ["事件摘要", "代表观点", "证据清单", "风险提示", "待验证项"]},
        ],
        "real": "评论时间序列与声量（时间窗内评论数）、热词、事件相关评论聚类与代表样本。",
        "pending": "全平台真实声量与增幅、传播路径（短视频/论坛）、事件复盘模板与行业报告样例。",
        "cta": '<a class="btn btn-demo" href="/login?redirect=/hotspot">进入数据工具 · 看热点</a><a class="btn btn-ghost" href="/ai-game-opinion-monitoring-system">了解监测系统</a>',
    },
    {
        "url": "/game-monetization-controversy-monitoring",
        "title": "游戏商业化争议舆情监测 | Game recharge controversy evaluation",
        "description": "游戏氪金、充值、活动福利与数值平衡争议的舆情监测：区分价格、信息透明、获得感、数值平衡与活动规则诉求，支持证据与反向证据并呈现玩家原话。",
        "keywords": "Game recharge controversy evaluation,Character numerical balance public opinion,游戏氪金舆情,充值争议,游戏数值平衡舆情",
        "h1": "¥ 游戏商业化争议舆情监测",
        "sub": "针对氪金、充值、礼包价值、概率认知、角色强度与活动福利等争议场景，精细分类并呈现支持证据、反向证据与玩家原话。",
        "badges": [{"type": "keyword", "text": "主关键词：Game recharge controversy evaluation"}],
        "section_heading": "商业化争议分析",
        "sections": [
            {"title": "高频争议场景", "text": "", "list": ["充值机制 / 价格", "礼包价值 / 概率认知", "角色强度 / 数值平衡", "活动福利 / 规则"]},
            {"title": "可能影响", "text": "可能关联口碑、留存与付费体验，但不能直接推断经营结果。"},
            {"title": "精细分类", "text": "", "list": ["价格诉求", "信息透明", "获得感", "数值平衡", "活动规则"]},
            {"title": "运营优化参考", "text": "呈现支持证据、反向证据和玩家原话，最终方案由业务人员确定。"},
        ],
        "real": "氪金/平衡/概率等主题聚类、争议评论声量与代表样本、正反观点分布。",
        "pending": "商业化舆情优化方案、数值调整参考案例、对收入与留存的实际影响。",
        "cta": '<a class="btn btn-demo" href="/login?redirect=/guide">进入数据工具 · 分析争议</a><a class="btn btn-ghost" href="/ai-game-opinion-monitoring-system">了解监测系统</a>',
    },
    {
        "url": "/cross-platform-game-opinion-aggregation",
        "title": "跨平台游戏舆情聚合与预警 | Cross-platform game public opinion aggregation",
        "description": "跨平台游戏舆情聚合与智能预警：统一保存来源平台、发布时间、原文 ID、链接与采集时间，按规则阈值与 AI 分类分级预警，适配版本发布与热点争议监测。",
        "keywords": "Cross-platform game public opinion aggregation,Game public opinion early warning system,跨平台舆情聚合,游戏舆情预警系统,多平台口碑监控",
        "h1": "◎ 跨平台游戏舆情聚合与预警",
        "sub": "把分散在社区、论坛与媒体中的舆情统一聚合，保存来源平台、时间、原文 ID 与链接；规则阈值 + AI 分类共同产生分级预警。",
        "badges": [{"type": "keyword", "text": "主关键词：Cross-platform game public opinion aggregation"}],
        "section_heading": "聚合与预警方案",
        "sections": [
            {"title": "分散监控痛点", "text": "社区、论坛、短视频和媒体内容分散，时间与口径不一致。"},
            {"title": "公开渠道聚合", "text": "", "list": ["统一保存来源平台", "发布时间", "原文 ID / 链接", "采集时间"]},
            {"title": "分级预警机制", "text": "由规则阈值与 AI 分类共同产生提示；具体规则待业务确认。"},
            {"title": "运营适配场景", "text": "", "list": ["版本发布", "服务器异常", "热点争议", "商业化活动监测"]},
        ],
        "real": "已接入平台（Steam / TapTap / Google Play）评论聚合、跨平台对比、按主题/情感聚合预警。",
        "pending": "短视频/论坛等更多平台覆盖、预警分级规则明细、定制化服务内容。",
        "cta": '<a class="btn btn-demo" href="/login?redirect=/dashboard">进入数据工具 · 看板</a><a class="btn btn-ghost" href="/ai-game-opinion-monitoring-system">了解监测系统</a>',
    },
]


_NEXT_STEPS = {
    "/game-public-opinion-ai-analysis": [
        {"title": "深入了解 AI 监测系统", "href": "/ai-game-opinion-monitoring-system",
         "desc": "查看系统功能、效率对比与适用用户，判断是否匹配你的场景。"},
        {"title": "按场景了解能力", "href": "/game-negative-public-opinion-monitoring",
         "desc": "负面风险 / 玩家体验 / 热点追踪 / 商业化争议 / 跨平台聚合 5 大内容页。"},
        {"title": "开始体验", "href": "/guide",
         "desc": "登录后进入分析向导，用公开评论跑一份真实舆情报告。"},
    ],
    "/ai-game-opinion-monitoring-system": [
        {"title": "回到平台总览", "href": "/game-public-opinion-ai-analysis",
         "desc": "从全站入口重新了解平台定位与整体能力。"},
        {"title": "按场景了解能力", "href": "/game-negative-public-opinion-monitoring",
         "desc": "负面风险 / 玩家体验 / 热点追踪 / 商业化争议 / 跨平台聚合。"},
        {"title": "预约试用 / Demo", "href": "/pricing",
         "desc": "提交试用申请，体验 AI 舆情监测能力。"},
    ],
    "/game-negative-public-opinion-monitoring": [
        {"title": "了解 AI 监测系统", "href": "/ai-game-opinion-monitoring-system",
         "desc": "把负面风险识别接入系统化的 AI 舆情监测。"},
        {"title": "回到平台总览", "href": "/game-public-opinion-ai-analysis",
         "desc": "查看平台整体能力与其它场景。"},
        {"title": "开始体验 · 查看负面预警", "href": "/dashboard",
         "desc": "登录后进入看板，查看基于公开评论的预警与趋势。"},
    ],
    "/mobile-game-player-experience-analysis": [
        {"title": "了解 AI 监测系统", "href": "/ai-game-opinion-monitoring-system",
         "desc": "把玩家体验分析纳入系统化监测。"},
        {"title": "回到平台总览", "href": "/game-public-opinion-ai-analysis",
         "desc": "查看平台整体能力与其它场景。"},
        {"title": "开始体验 · 分析玩家体验", "href": "/guide",
         "desc": "登录后进入分析向导，聚类 BUG/卡顿/掉线等反馈。"},
    ],
    "/game-hot-event-tracking": [
        {"title": "了解 AI 监测系统", "href": "/ai-game-opinion-monitoring-system",
         "desc": "把热点追踪接入系统化的 AI 舆情监测。"},
        {"title": "回到平台总览", "href": "/game-public-opinion-ai-analysis",
         "desc": "查看平台整体能力与其它场景。"},
        {"title": "查看热点深析", "href": "/hotspot",
         "desc": "登录后浏览基于公开数据的 AI 行业热点文章。"},
    ],
    "/game-monetization-controversy-monitoring": [
        {"title": "了解 AI 监测系统", "href": "/ai-game-opinion-monitoring-system",
         "desc": "把商业化争议监测纳入系统化方案。"},
        {"title": "回到平台总览", "href": "/game-public-opinion-ai-analysis",
         "desc": "查看平台整体能力与其它场景。"},
        {"title": "开始体验 · 分析商业化舆情", "href": "/guide",
         "desc": "登录后进入分析向导，聚类氪金/平衡等争议反馈。"},
    ],
    "/cross-platform-game-opinion-aggregation": [
        {"title": "了解 AI 监测系统", "href": "/ai-game-opinion-monitoring-system",
         "desc": "把跨平台聚合与预警接入系统化方案。"},
        {"title": "回到平台总览", "href": "/game-public-opinion-ai-analysis",
         "desc": "查看平台整体能力与其它场景。"},
        {"title": "查看看板", "href": "/dashboard",
         "desc": "登录后进入看板，查看跨平台聚合数据。"},
    ],
}


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for page in PAGES:
        page["next_steps"] = _NEXT_STEPS[page["url"]]
        html = render(page)
        path = OUT_DIR / (page["url"].strip("/") + ".html")
        path.write_text(html, encoding="utf-8")
        print(f"  ✓ {path.name} ({len(html)} bytes)")
    print(f"\n共生成 {len(PAGES)} 个页面 -> {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

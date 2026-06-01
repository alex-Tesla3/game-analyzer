#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MVP 报告生成模块

从 JSON Lines 数据生成 Markdown 格式的分析报告。
"""

from typing import List, Dict, Any, Optional
from collections import Counter
import json


def generate_report(input_file: str, output_file: str = None) -> str:
    """
    从 JSON Lines 数据生成 Markdown 分析报告。

    参数：
        input_file: JSON Lines 数据文件
        output_file: 输出 Markdown 文件（可选，默认打印到 stdout）

    返回：
        生成的 Markdown 报告字符串
    """
    
    # 读取数据
    with open(input_file, "r", encoding="utf-8") as f:
        items = [json.loads(line.strip()) for line in f if line.strip()]
    
    # 收集统计信息
    stats = _collect_stats(items)
    
    # 生成报告内容
    report = _generate_report_content(stats)
    
    # 写入文件
    if output_file:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(report)
    
    return report


def _collect_stats(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    收集数据统计信息
    """
    
    stats = {
        "total": len(items),
        "sentiment": {
            "positive": sum(1 for item in items if item.get("sentiment") == "positive"),
            "negative": sum(1 for item in items if item.get("sentiment") == "negative"),
            "neutral": sum(1 for item in items if item.get("sentiment") == "neutral" or not item.get("sentiment")),
        },
        "product": Counter(),
        "platform": Counter(),
        "score": [],
        "topics": Counter(),
    }
    
    # 产品分布
    for item in items:
        product = str(item.get("product", "未知产品"))
        stats["product"][product] += 1
    
    # 平台分布
    for item in items:
        platform = str(item.get("platform", "未知平台"))
        stats["platform"][platform] += 1
    
    # 评分统计
    for item in items:
        score = item.get("score")
        if score is not None:
            stats["score"].append(float(score))
    
    # 评分统计
    if stats["score"]:
        min_score = min(stats["score"])
        max_score = max(stats["score"])
        avg_score = sum(stats["score"]) / len(stats["score"])
        stats["score_stats"] = {
            "min": min_score,
            "max": max_score,
            "avg": avg_score,
            "count": len(stats["score"]),
        }
    
    # Top 产品
    stats["top_products"] = [{"product": k, "count": v} for k, v in stats["product"].most_common(5)]
    
    # Top 平台
    stats["top_platforms"] = [{"platform": k, "count": v} for k, v in stats["platform"].most_common(5)]
    
    # 情感比例
    total_sentiment = stats["sentiment"]["positive"] + stats["sentiment"]["negative"]
    stats["sentiment_ratio"] = {
        "positive": (stats["sentiment"]["positive"] / total_sentiment * 100) if total_sentiment else 0,
        "negative": (stats["sentiment"]["negative"] / total_sentiment * 100) if total_sentiment else 0,
    }
    
    return stats


def _generate_report_content(stats: Dict[str, Any]) -> str:
    """
    生成 Markdown 报告内容
    """
    
    lines = [
        "# 📊 游戏评价分析报告",
        "",
        "## 📈 总体概览",
        "",
        f"- 总评论数：{stats['total']} 条",
    ]
    
    # 情感分布
    sentiment_data = [
        ("正面评价", stats["sentiment"]["positive"]),
        ("负面评价", stats["sentiment"]["negative"]),
        ("中性/缺失", stats["sentiment"]["neutral"]),
    ]
    for label, count in sentiment_data:
        emoji = "✅" if "正面" in label else "❌" if "负面" in label else "🟡"
        lines.append(f"- {emoji} {label}：{count} 条")
    
    # 评分统计
    if "score_stats" in stats:
        score = stats["score_stats"]
        lines.extend([
            "",
            "## ⭐ 评分统计",
            "",
            f"- 平均评分：{score['avg']:.2f}",
            f"- 最低评分：{score['min']:.2f}",
            f"- 最高评分：{score['max']:.2f}",
        ])
    
    # Top 产品
    lines.extend([
        "",
        "## 🎮 热门产品",
        "",
    ])
    for item in stats["top_products"]:
        lines.append(f"- {item['product']}: {item['count']} 条评价")
    
    # Top 平台
    lines.extend([
        "",
        "## 🌐 平台分布",
        "",
    ])
    for item in stats["top_platforms"]:
        lines.append(f"- {item['platform']}: {item['count']} 条评价")
    
    # 情感比例
    if "sentiment_ratio" in stats:
        lines.extend([
            "",
            "## 📊 情感比例",
            "",
            f"- 正面评价：{stats['sentiment_ratio']['positive']:.1f}%",
            f"- 负面评价：{stats['sentiment_ratio']['negative']:.1f}%",
        ])
    
    return "\n".join(lines)


def generate_detailed_report(input_file: str, output_file: str = None) -> str:
    """
    生成详细的分析报告（包含示例评论）。

    参数：
        input_file: JSON Lines 数据文件
        output_file: 输出 Markdown 文件

    返回：
        生成的 Markdown 报告字符串
    """
    
    # 读取数据
    with open(input_file, "r", encoding="utf-8") as f:
        items = [json.loads(line.strip()) for line in f if line.strip()]
    
    # 收集统计信息
    stats = _collect_stats(items)
    
    # 生成详细报告
    lines = [
        "# 📊 游戏评价分析报告",
        "",
        "---",
        "",
        f"`来源`: {input_file}",
        f"`总评论数`: {stats['total']}",
        "",
        "=" * 50,
        "",
    ]
    
    # 总体概览
    lines.extend([
        "## 📈 总体概览",
        "",
        f"- **总评论数**: {stats['total']} 条",
        f"- **正面评价**: {stats['sentiment']['positive']} 条",
        f"- **负面评价**: {stats['sentiment']['negative']} 条",
        f"- **中性/缺失**: {stats['sentiment']['neutral']} 条",
    ])
    
    # 情感比例
    total_sentiment = stats["sentiment"]["positive"] + stats["sentiment"]["negative"]
    if total_sentiment:
        positive_pct = stats["sentiment"]["positive"] / total_sentiment * 100
        negative_pct = stats["sentiment"]["negative"] / total_sentiment * 100
        lines.extend([
            "",
            f"- **正面评价比例**: {positive_pct:.1f}%",
            f"- **负面评价比例**: {negative_pct:.1f}%",
        ])
    
    # 评分统计
    if "score_stats" in stats:
        score = stats["score_stats"]
        lines.extend([
            "",
            "### ⭐ 评分统计",
            "",
            f"- **平均评分**: {score['avg']:.2f}/5.0",
            f"- **最低评分**: {score['min']:.2f}",
            f"- **最高评分**: {score['max']:.2f}",
            f"- **评分数量**: {score['count']} 条",
        ])
    
    # 产品分布
    lines.extend([
        "",
        "## 🎮 产品分布",
        "",
        "| 产品 | 评价数 |",
        "|------|--------|",
    ])
    
    # Top 10 产品，按数量降序
    for product, count in sorted(stats["product"].most_common(10), key=lambda x: x[1], reverse=True):
        lines.append(f"| {product} | {count} |")
    
    # 平台分布
    lines.extend([
        "",
        "## 🌐 平台分布",
        "",
        "| 平台 | 评价数 |",
        "|------|--------|",
    ])
    
    for platform, count in sorted(stats["platform"].most_common(10), key=lambda x: x[1], reverse=True):
        lines.append(f"| {platform} | {count} |")
    
    # 示例评论
    lines.extend([
        "",
        "## 💬 示例评论",
        "",
        "### 正面评价",
        "",
    ])
    
    positive_items = [item for item in items if item.get("sentiment") == "positive"]
    for example in positive_items[:3]:  # Top 3 正面示例
        content = example.get("content", "无内容")[0:200]
        lines.append(f"- `>{example.get('comment_id', '无 ID')}`: {content[:50]}...")
    
    lines.extend([
        "",
        "### 负面评价",
        "",
    ])
    
    negative_items = [item for item in items if item.get("sentiment") == "negative"]
    for example in negative_items[:3]:  # Top 3 负面示例
        content = example.get("content", "无内容")[0:200]
        lines.append(f"- `>{example.get('comment_id', '无 ID')}`: {content[:50]}...")
    
    lines.extend([
        "",
        "---",
        "",
    ])
    
    report = "\n".join(lines)
    
    # 写入文件
    if output_file:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(report)
    
    return report


def stream_report(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    流式生成报告（适合大数据集）。

    参数：
        items: 数据列表

    返回：
        统计信息和报告内容
    """
    
    stats = _collect_stats(items)
    report = generate_report.__code__(stats)  # type: ignore
    
    return {
        "items_processed": len(items),
        "statistics": stats,
        "report": report,
    }

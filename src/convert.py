#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MVP 数据转换模块

将原始的 API 调用结果转换为标准化的 JSON Lines 格式。
"""

from typing import List, Dict, Any, Optional
import json
from pathlib import Path


def convert_to_jsonlines(items: List[Dict[str, Any]], output_file: str) -> int:
    """
    将原始数据转换为标准化的 JSON Lines 格式并写入文件。

    参数：
        items: 原始数据列表，包含以下任意字段：
            - comment_id: 评论 ID
            - product: 产品标识
            - sentiment: 情绪（positive/negative）
            - content: 评论内容
            - user_role: 用户角色（可选）
            - score: 评分（可选）
            - platform: 平台（steam/epic/wechatgames/apple/等）
            - extract_time: 提取时间（可选）
            - 其他来自 API 的字段
        output_file: 输出 JSON Lines 文件路径

    返回：
        写入文件的行号
    """
    
    written_count = 0
    
    # 输出文件路径
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, "w", encoding="utf-8") as f:
        for item in items:
            # 标准化字段名
            standardized_item = _standardize_item(item)
            if standardized_item:
                # 写入 JSON 行
                json.dump(standardized_item, f, ensure_ascii=False, separators=(",", ":"))
                f.write("\n")
                written_count += 1
    
    return written_count


def _standardize_item(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    标准化单个记录：删除原始字段，添加 MVP 所需字段。
    
    保留字段：
        - comment_id
        - product
        - sentiment
        - content
        - user_role (optional)
        - score (optional)
        - platform (optional)
        - extract_time (optional)
        - 其他重要字段...
    
    删除字段：
        - request_id
        - scrape_status
        - raw_url
        - 其他临时字段
    """
    
    # 需要保留的字段
    keep_fields = {
        "comment_id",
        "product",
        "sentiment",
        "content",
        "user_role",
        "score",
        "platform",
        "extract_time",
    }
    
    # 需要转换字段名的映射
    field_mapping = {
        "产品": "product",
        "评论 ID": "comment_id",
        "评论 id": "comment_id",
        "评论内容": "content",
        "情绪": "sentiment",
        "情感": "sentiment",
        "情感评分": "sentiment",
        "情感评分": "sentiment",
        "评分": "score",
        "user_role": "user_role",
        "platform": "platform",
        "提取时间": "extract_time",
        "提取时间": "extract_time",
    }
    
    # 过滤并转换字段
    standardized = {
        field_mapping.get(key, key): value
        for key, value in item.items()
        if (key in field_mapping or key in keep_fields) and value
    }
    
    return standardized or None


def stream_jsonlines(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    流式转换大量数据（不加载到内存）。

    适合处理大文件或无限数据流。

    返回：
        - items_written: 已写入的行数
        - output_file: 输出文件路径
        - stats: 转换统计信息
    """
    
    # 输出文件路径
    output_path = items[0].get("output_file", "output.jsonl")
    
    items_written = 0
    
    with open(output_path, "w", encoding="utf-8") as f:
        for item in items:
            standardized_item = _standardize_item(item)
            if standardized_item:
                json.dump(standardized_item, f, ensure_ascii=False, separators=(",", ":"))
                f.write("\n")
                items_written += 1
    
    return {
        "items_written": items_written,
        "output_file": output_path,
        "stats": _collect_stats(items),
    }


def _collect_stats(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    收集统计信息：
        - 总行数
        - 情绪分布
        - 产品分布
        - 平台分布
        - 评分统计
    """
    
    from collections import Counter
    
    stats = {
        "total": len(items),
        "sentiment": Counter(),
        "product": Counter(),
        "platform": Counter(),
    }
    
    for item in items:
        sentiment = item.get("sentiment")
        if sentiment:
            stats["sentiment"][sentiment] += 1
        
        product = item.get("product")
        if product:
            stats["product"][str(product)] += 1
        
        platform = item.get("platform")
        if platform:
            stats["platform"][str(platform)] += 1
    
    # 计算评分统计
    scores = [float(item.get("score", 0)) for item in items if item.get("score")]
    if scores:
        stats["score"] = {
            "min": min(scores),
            "max": max(scores),
            "avg": sum(scores) / len(scores),
            "count": len(scores),
        }
    
    return stats


def batch_convert(input_file: str, output_file: str) -> Dict[str, Any]:
    """
    批量转换 JSON 文件列表。

    参数：
        input_file: JSON 文件路径或文件列表
        output_file: 输出 JSON Lines 文件路径

    返回：
        转换统计信息
    """
    
    import glob
    
    # 处理单个文件或文件列表
    if "*" in input_file:
        input_files = sorted(glob.glob(input_file))
    else:
        input_files = [input_file]
    
    all_items = []
    
    for input_path in input_files:
        with open(input_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    all_items.append(json.loads(line))
    
    # 转换并写入
    stats = _collect_stats(all_items)
    stats["input_files"] = len(input_files)
    stats["output_file"] = output_file
    
    write_result = convert_to_jsonlines(all_items, output_file)
    stats["items_written"] = write_result
    
    # 覆盖输出文件的统计信息
    with open(output_file, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]
    stats["line_count"] = len(lines)
    
    return stats

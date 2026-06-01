#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MVP 数据清洗脚本

从 CSV 文件提取需要的字段，清理无效数据，并转换为 JSON Lines 格式。
保留以下核心字段：
- comment_id, product, sentiment, content
- 用户角色 (可选)
- 评分 (可选)
- 提取时间 (可选)

清理规则：
- 删除 sentiment 为 neutral 的记录
- 删除 content 为空或只有换行的记录
- 删除缺失必要字段（comment_id, product）的记录
"""

import csv
import json
import sys
from pathlib import Path
from typing import Optional

# 需要保留的字段映射
REQUIRED_FIELDS = {
    "comment_id": str,
    "product": str,
    "sentiment": str,
    "content": str,
}

OPTIONAL_FIELDS = {
    "用户角色": str,
    "评分": Optional[float],
    "提取时间": str,
}

# 情绪标准化映射
SENTIMENT_MAP = {
    "positive": "positive",
    "正面": "positive",
    "好评": "positive",
    "好": "positive",
    "棒": "positive",
    "喜欢": "positive",
    "推荐": "positive",
    "positive": "positive",
    
    "negative": "negative",
    "负面": "negative",
    "差评": "negative",
    "坏": "negative",
    "讨厌": "negative",
    "不好": "negative",
    "negative": "negative",
    
    "neutral": "neutral",
    "中性": "neutral",
}


def parse_product(product_raw: str) -> str:
    """解析产品标识，支持多种格式"""
    if not product_raw:
        return "未指定产品"
    
    product_str = product_raw.strip().lower()
    
    # 尝试映射产品标识
    product_mapping = {
        "steam_game": "Steam",
        "steam 游戏": "Steam",
        "steam": "Steam",
        "store": "Steam",
        "商店": "Steam",
        
        "epic": "Epic",
        "epic 游戏": "Epic",
        "epic 商店": "Epic",
        
        "wechatgames": "Wechat",
        "wechat 小游戏": "Wechat",
        "小程序游戏": "Wechat",
        "微信游戏": "Wechat",
        
        "apple_app_store": "AppStore",
        "apple 应用商店": "AppStore",
        "ios": "AppStore",
        "iphone": "AppStore",
        "appstore": "AppStore",
        "itms": "AppStore",
        
        "qqgame": "Qq",
        "qq 游戏": "Qq",
        "qqlive": "Qq",
        
        "bilibili": "Bilibili",
        "b 站": "Bilibili",
        "哔哩哔哩": "Bilibili",
        "bilibili 游戏": "Bilibili",
        
        "mobile": "Mobile",
        "android": "Mobile",
    }
    
    result = product_mapping.get(product_str, product_raw)
    return result


def is_valid_content(content: str) -> bool:
    """检查内容是否有效"""
    if not content:
        return False
    
    # 删除纯空白字符
    if content.strip() == "":
        return False
    
    # 删除只有标点符号的行
    stripped = content.strip()
    if stripped and not any(c.isalnum() for c in stripped):
        return False
    
    return True


def parse_sentiment(sentiment: str) -> Optional[str]:
    """标准化情绪标识，删除中性情绪"""
    sentiment_lower = sentiment.lower()
    mapped = SENTIMENT_MAP.get(sentiment_lower, sentiment_lower)
    
    # 删除中性情绪的评论
    if mapped in ("neutral", "中性", ""):
        return None
    
    return str(mapped)


def parse_score(score_raw: str) -> Optional[float]:
    """解析评分"""
    if not score_raw:
        return None
    
    try:
        score = float(score_raw)
        return score if 0 <= score <= 5 else None
    except (ValueError, TypeError):
        return None


def process_csv(input_path: str, output_path: str) -> dict[str, int]:
    """处理 CSV 文件，输出 JSON Lines 格式"""
    
    if not Path(input_path).exists():
        print(f"[ERROR] 输入文件不存在：{input_path}", file=sys.stderr)
        return {"input": 0, "output": 0, "removed": 0, "invalid": 0}
    
    stats = {
        "input": 0,
        "output": 0,
        "removed": 0,
        "invalid": 0,
    }
    
    input_file = Path(input_path)
    output_file = Path(output_path)
    
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(input_file, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            stats["input"] += 1
            
            # 检查必需字段
            if any(
                not (row.get(field) or "").strip()
                for field in REQUIRED_FIELDS
            ):
                stats["invalid"] += 1
                continue
            
            # 检查情绪标识
            sentiment = row.get("sentiment", "")
            sentiment_normalized = parse_sentiment(sentiment)
            if sentiment_normalized is None:
                stats["removed"] += 1
                continue
            
            # 检查内容有效性
            content = row.get("content", "")
            if not is_valid_content(content):
                stats["invalid"] += 1
                continue
            
            # 处理产品标识
            product = parse_product(row.get("product", ""))
            
            # 处理评分
            score = parse_score(row.get("评分"))  # type: ignore
            
            # 创建输出记录
            output_record = {
                "comment_id": row.get("comment_id", "").strip(),
                "product": product,
                "sentiment": sentiment_normalized,
                "content": row.get("content", "").strip(),
            }
            
            # 添加可选字段
            for field, dtype in OPTIONAL_FIELDS.items():
                if field == "评分":
                    output_record[field] = parse_score(row.get(field))
                elif field == "提取时间":
                    if row.get(field):
                        output_record[field] = row[field].strip()
                else:
                    raw_value = row.get(field)
                    if raw_value:
                        output_record[field] = raw_value.strip()
            
            # 写入输出文件
            with open(output_file, "a", encoding="utf-8") as out_f:
                json.dump(output_record, out_f, ensure_ascii=False, separators=(",", ":"))
                out_f.write("\n")
            
            stats["output"] += 1
    
    return stats


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="MVP 数据清洗脚本：从 CSV 提取需要的字段并清理无效数据"
    )
    
    parser.add_argument(
        "input_file",
        nargs="?",
        default="reviews_data.csv",
        help="输入的 CSV 文件路径",
    )
    
    parser.add_argument(
        "output_file",
        nargs="?",
        default="reviews_data_mvp.jsonl",
        help="输出的 JSON Lines 文件路径",
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="显示详细信息",
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只统计不写入输出文件",
    )
    
    args = parser.parse_args()
    
    print(f"MVP 数据清洗脚本")
    print(f"输入文件：{args.input_file}")
    print(f"输出文件：{args.output_file}")
    print()
    
    stats = process_csv(args.input_file, args.output_file if not args.dry_run else "N/A")
    
    print(f"处理完成")
    print(f"  输入行数：{stats['input']}")
    print(f"  输出行数：{stats['output']}")
    print(f"  删除行数：{stats['removed']}（中性情绪）")
    print(f"  无效行数：{stats['invalid']}（缺少字段或无效内容）")
    print()
    
    if not args.dry_run:
        print(f"输出文件已保存：{args.output_file}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
游戏产品数据分析平台 CLI

用法：
    python -m game_analyzer [子命令] [参数...]

子列表:
    convert data.csv data.jsonl
    clean data.csv data.jsonl
    report data.jsonl -o report.md
    batch *.jsonl -o merged.jsonl
    summarize data.jsonl
    analyze data.jsonl -o analysis.md
    info
"""

import argparse
import sys
from pathlib import Path

from src.convert import convert_to_jsonlines
from src.report import generate_report, generate_detailed_report

__version__ = "0.1.0"


def main():
    parser = argparse.ArgumentParser(
        prog="game_analyzer",
        description="游戏产品数据分析平台",
    )
    parser.add_argument("command", nargs="?", choices=[
        "convert",
        "report",
        "summary",
        "analyze",
        "info",
    ])
    parser.add_argument("--version", action="version", version="v" + __version__)
    parser.add_argument("input", nargs="?", default="data.jsonl")
    parser.add_argument("output", nargs="?")
    args = parser.parse_args()
    
    if args.command == "info":
        print(f"\n游戏产品数据分析平台 v{__version__}")
        print("\n命令:")
        print("  convert data.csv data.jsonl")
        print("  report data.jsonl -o report.md")
        print("  summary data.jsonl")
        print("  info")
        return
    
    elif args.command == "convert":
        return convert_to_jsonlines(
            [args.input],  # 简化：只支持单个文件
            args.output,
        )
    
    elif args.command == "report":
        if args.output == "-":
            print(generate_report(args.input))
        else:
            with open(args.output, "w") as f:
                f.write(generate_report(args.input))
    
    elif args.command == "summary":
        print(generate_report(args.input))
    
    elif args.command == "analyze":
        print("分析命令正在开发中...")
        print(generate_report(args.input))


if __name__ == "__main__":
    main()

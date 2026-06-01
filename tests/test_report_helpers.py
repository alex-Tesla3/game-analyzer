"""Tests for report helper product name resolution."""

from __future__ import annotations

from src.services.report_helpers import (
    generate_html_period_report,
    generate_product_details,
    generate_report_summary,
    product_label_map,
)


def test_product_label_map_uses_product_name():
    metrics = [
        {"product": "730", "product_name": "Counter-Strike 2", "metric": "抓取评论数", "值": 20},
        {"product": "570", "product_name": "Dota 2", "metric": "抓取评论数", "值": 15},
    ]
    labels = product_label_map(metrics)
    assert labels["730"] == "Counter-Strike 2"
    assert labels["570"] == "Dota 2"


def test_generate_product_details_uses_real_names():
    metrics = [
        {"product": "730", "product_name": "Counter-Strike 2", "metric": "抓取评论数", "值": 20},
        {"product": "730", "product_name": "Counter-Strike 2", "metric": "Steam汇总好评率", "值": 80},
    ]
    details = generate_product_details(metrics)
    assert len(details) == 1
    assert details[0]["product"] == "Counter-Strike 2"


def test_generate_report_summary_lists_real_names():
    metrics = [
        {"product": "730", "product_name": "Counter-Strike 2", "metric": "抓取评论数", "值": 20},
    ]
    summary = generate_report_summary(metrics, [], "daily")
    assert "Counter-Strike 2" in summary
    assert "game_a" not in summary


def test_generate_html_period_report_includes_product_names():
    metrics = [
        {"product": "730", "product_name": "Counter-Strike 2", "metric": "抓取评论数", "值": 20},
        {"product": "730", "product_name": "Counter-Strike 2", "metric": "Steam汇总好评率", "值": 85.5},
    ]
    html = generate_html_period_report("daily", metrics, ["730"])
    assert "Counter-Strike 2" in html
    assert "产品范围: Counter-Strike 2" in html

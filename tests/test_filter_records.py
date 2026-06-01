"""Tests for shared record filtering helpers."""

from src.mvp_data import filter_records, metric_matches_period


def test_metric_matches_period_aliases():
    assert metric_matches_period({"cycle": "Week 21"}, "week_21")
    assert metric_matches_period({"cycle": "week_22"}, "week_22")
    assert metric_matches_period({"cycle": "Q2"}, "quarter_2")
    assert metric_matches_period({"cycle": ""}, "quarter_2")
    assert not metric_matches_period({"cycle": "week_22"}, "week_21")


def test_filter_records_normalizes_steam_product_ids():
    metrics = [
        {"product": "730", "cycle": "week_22", "metric": "用户总下载量"},
        {"product": "game_b", "cycle": "week_22", "metric": "用户总下载量"},
    ]
    _, fm = filter_records([], metrics, products=["steam_730"])
    assert len(fm) == 1 and fm[0]["product"] == "730"


def test_filter_records_product_and_period():
    metrics = [
        {"product": "game_a", "cycle": "week_22", "metric": "用户总下载量"},
        {"product": "game_b", "cycle": "Week 21", "metric": "用户总下载量"},
    ]
    comments = [
        {"product": "game_a", "情绪": "positive", "内容": "good"},
        {"product": "game_b", "情绪": "negative", "内容": "bad"},
    ]
    fc, fm = filter_records(comments, metrics, product="game_a", time_period="week_22")
    assert len(fc) == 1 and fc[0]["product"] == "game_a"
    assert len(fm) == 1 and fm[0]["cycle"] == "week_22"

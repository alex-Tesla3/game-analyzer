"""Data source resolution and filter usability."""

from src.data_resolution import comments_dataset_usable, cached_metrics_usable
from src.mvp_data import filter_records, product_matches


def test_product_matches_numeric_ids():
    row = {"product": "730", "product_name": "Game"}
    assert product_matches(row, "730")
    assert not product_matches(row, "game_a")


def test_filter_steam_channel_metrics():
    metrics = [
        {"product": "game_a", "channel": "Steam", "cycle": "week_22", "metric": "用户总下载量"},
        {"product": "game_b", "channel": "Steam", "cycle": "week_21", "metric": "用户总下载量"},
    ]
    _, filtered = filter_records([], metrics, product="game_a", time_period="week_22")
    assert len(filtered) == 1
    assert filtered[0]["product"] == "game_a"


def test_comments_dataset_rejects_test_only_cache():
    assert not comments_dataset_usable([{"product": "test", "内容": "x"}])
    assert comments_dataset_usable([{"product": "730", "内容": "x"}])


def test_cached_metrics_accepts_mvp_style_products():
    rows = [{"product": "730", "metric": "steam_positive_rate", "值": 80}]
    assert cached_metrics_usable(rows)

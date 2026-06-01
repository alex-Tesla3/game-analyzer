"""Tests for dataset usability and catalog derivation."""

from src.data_catalog import derive_data_catalog, enrich_catalog_from_context, metrics_dataset_usable


def test_metrics_dataset_usable_rejects_test_cache():
    cache_rows = [{"product": "test", "platform": "steam", "metric": "players", "值": 1}]
    assert not metrics_dataset_usable(cache_rows)


def test_metrics_dataset_usable_accepts_mock_shape():
    mock_rows = [{"product": "game_a", "metric": "用户总下载量", "值": 100}]
    assert metrics_dataset_usable(mock_rows)


def test_derive_data_catalog_from_mvp_shape():
    comments = [{"product": "730", "product_name": "CS2", "情绪": "positive", "内容": "ok"}]
    metrics = [{"product": "730", "product_name": "CS2", "cycle": "2026-05-28", "metric": "抓取评论数", "值": 10}]
    catalog = derive_data_catalog(comments, metrics)
    assert catalog["products"][0]["id"] == "730"
    assert catalog["products"][0]["name"] == "CS2"
    assert catalog["time_periods"][0]["id"] == "2026-05-28"


def test_derive_data_catalog_keeps_comment_name_when_metrics_missing_label():
    comments = [{"product": "10", "product_name": "Counter-Strike", "内容": "ok"}]
    metrics = [{"product": "10", "metric": "抓取评论数", "值": 2}]
    catalog = derive_data_catalog(comments, metrics)
    assert catalog["products"][0]["name"] == "Counter-Strike"
    assert catalog["products"][0]["genre"] == "FPS"


def test_derive_data_catalog_falls_back_to_steam_name_table():
    metrics = [{"product": "730", "metric": "抓取评论数", "值": 1}]
    catalog = derive_data_catalog([], metrics)
    assert catalog["products"][0]["name"] == "Counter-Strike 2"


def test_enrich_catalog_adds_genre_presets():
    catalog = derive_data_catalog(
        [{"product": "10", "product_name": "Counter-Strike", "内容": "ok"}],
        [{"product": "10", "metric": "抓取评论数", "值": 1}],
    )
    enriched = enrich_catalog_from_context(catalog, username="demo")
    genre_ids = {g["id"] for g in enriched["genres"]}
    assert "FPS" in genre_ids
    assert "MOBA" in genre_ids
    assert len(genre_ids) > 1


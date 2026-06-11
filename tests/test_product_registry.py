"""Tests for crawl product registry and custom game products."""

from __future__ import annotations

from src.product_registry import (
    add_custom_product,
    apply_product_display_names,
    get_mvp_presets,
    load_custom_products,
    lookup_display_name,
    parse_product_name_overrides,
    resolve_mvp_crawl_targets,
    save_custom_products,
)
from src.services.google_play_pipeline import resolve_google_play_inputs, run_google_play_pipeline
from src.services.taptap_pipeline import resolve_taptap_inputs, run_taptap_pipeline


def test_registry_last_war_google_play_alias():
    out = resolve_google_play_inputs("last war")
    assert out["success"] is True
    assert out["app_ids"] == ["com.fun.lastwar.gp"]


def test_registry_dark_war_google_play_alias():
    out = resolve_google_play_inputs("dark war")
    assert out["success"] is True
    assert out["app_ids"] == ["com.readygo.dark.gp"]


def test_registry_last_beacon_google_play_alias():
    out = resolve_google_play_inputs("last beacon")
    assert out["success"] is True
    assert out["app_ids"] == ["com.hnhs.endlesssea.gp"]


def test_registry_last_war_taptap_alias():
    out = resolve_taptap_inputs("last war")
    assert out["success"] is True
    assert out["app_ids"] == ["33569155"]


def test_lookup_display_name_prefers_registry():
    name = lookup_display_name("com.hnhs.endlesssea.gp", platform="google_play")
    assert name == "Last Beacon: Survival"


def test_parse_product_name_overrides_colon():
    parsed = parse_product_name_overrides("com.fun.lastwar.gp:我的Last War")
    assert parsed["com.fun.lastwar.gp"] == "我的Last War"


def test_apply_product_display_names_overrides_store_title():
    dataset = {
        "games": [{"package_id": "com.fun.lastwar.gp", "name": "Store Title", "platform": "Google Play"}],
        "comments": [
            {
                "product": "com.fun.lastwar.gp",
                "product_name": "Store Title",
                "platform": "Google Play",
            }
        ],
        "metrics": [],
    }
    apply_product_display_names(dataset, {"com.fun.lastwar.gp": "自定义 Last War"})
    assert dataset["comments"][0]["product_name"] == "自定义 Last War"
    assert dataset["games"][0]["name"] == "自定义 Last War"


def test_mvp_presets_include_last_war_dark_war_and_last_beacon():
    presets = get_mvp_presets()
    ids = {p["id"] for p in presets}
    assert "com.fun.lastwar.gp" in ids
    assert "com.readygo.dark.gp" in ids
    assert "com.hnhs.endlesssea.gp" in ids
    assert "33569155" in ids


def test_add_custom_product_persists(tmp_path, monkeypatch):
    path = tmp_path / "custom_products.json"
    monkeypatch.setattr("src.product_registry.custom_products_path", lambda: str(path))

    result = add_custom_product(
        display_name="My Custom SLG",
        platform="google_play",
        product_id="com.example.custom",
        genre="SLG",
    )
    assert result["success"] is True
    assert result["product"]["id"] == "com.example.custom"
    saved = load_custom_products()
    assert len(saved) == 1
    assert saved[0]["display_name"] == "My Custom SLG"


def test_add_custom_product_resolves_name(tmp_path, monkeypatch):
    path = tmp_path / "custom_products.json"
    monkeypatch.setattr("src.product_registry.custom_products_path", lambda: str(path))

    result = add_custom_product(display_name="Last Beacon", platform="google_play")
    assert result["product"]["id"] == "com.hnhs.endlesssea.gp"
    assert "Last Beacon" in result["product"]["name"] or result["product"]["name"]


def test_resolve_mvp_crawl_targets_by_game_name():
    app_ids, overrides, errors = resolve_mvp_crawl_targets("google_play", "", "last beacon")
    assert errors == []
    assert app_ids == ["com.hnhs.endlesssea.gp"]
    assert overrides == {}


def test_run_google_play_pipeline_uses_registry_display_name(tmp_path):
    out_dir = tmp_path / "mvp"
    result = run_google_play_pipeline(["com.readygo.dark.gp"], output_dir=str(out_dir))
    assert result["success"] is True
    metrics = result["dataset"]["metrics"]
    assert metrics[0]["product_name"] == "Dark War: Survival"


def test_run_taptap_pipeline_uses_registry_display_name(tmp_path):
    out_dir = tmp_path / "mvp"
    result = run_taptap_pipeline(["33569155"], output_dir=str(out_dir))
    assert result["success"] is True
    metrics = result["dataset"]["metrics"]
    assert metrics[0]["product_name"] == "Last War: Survival"

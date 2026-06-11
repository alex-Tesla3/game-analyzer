"""Product name resolution for analytics reports."""

from src.services.legacy_ai_report import generate_product_trends
from src.services.product_name_resolver import build_product_name_map, label_for_products


def test_build_product_name_map_includes_registry_products():
    names = build_product_name_map(["com.fun.lastwar.gp", "com.readygo.dark.gp"])
    assert "com.fun.lastwar.gp" in names
    assert "Last War" in names["com.fun.lastwar.gp"]


def test_label_for_products_joins_display_names():
    names = {"730": "Counter-Strike 2", "570": "Dota 2"}
    assert label_for_products(["730", "570"], names) == "Counter-Strike 2、Dota 2"


def test_generate_product_trends_uses_real_products_not_mock_fallback():
    names = build_product_name_map(["com.fun.lastwar.gp"])
    trends = generate_product_trends(["com.fun.lastwar.gp"], names)
    assert len(trends) == 1
    assert "Last War" in trends[0]["product"]
    assert "游戏A" not in trends[0]["product"]

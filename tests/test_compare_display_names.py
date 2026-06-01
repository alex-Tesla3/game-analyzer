"""Compare payload should resolve TapTap game_ids to display names."""

from __future__ import annotations

from unittest.mock import patch

from src.services.competitor_workbench import build_compare_payload, normalize_compare_id, resolve_compare_row


def test_normalize_compare_id_strips_taptap_prefix():
    assert normalize_compare_id("taptap_168332") == "168332"
    assert normalize_compare_id("steam_730") == "730"


def test_resolve_compare_row_taptap():
    game_id, product_id = resolve_compare_row("taptap_168332")
    assert game_id == "taptap_168332"
    assert product_id == "168332"


@patch("src.services.game_intel.GameLibraryRepository.get")
@patch("src.services.competitor_workbench.get_mvp_comments_and_metrics")
@patch("src.services.competitor_workbench.get_mvp_analysis")
@patch("src.services.competitor_workbench.mvp_validation_passed")
def test_build_compare_payload_uses_taptap_names(mock_valid, mock_analysis, mock_mvp, mock_get):
    mock_valid.return_value = True
    mock_analysis.return_value = {
        "product_reports": [
            {"product": "168332", "product_name": "原神", "positive_rate": 66.7, "sample_size": 3},
            {"product": "23167", "product_name": "王者荣耀", "positive_rate": 66.7, "sample_size": 3},
        ]
    }
    mock_mvp.return_value = ([], [], "taptap_public")

    def _library_get(game_id):
        names = {
            "taptap_168332": {"name": "原神", "source": "taptap_public", "genre": "RPG"},
            "taptap_23167": {"name": "王者荣耀", "source": "taptap_public", "genre": "MOBA"},
        }
        return names.get(game_id)

    mock_get.side_effect = _library_get

    payload = build_compare_payload(["taptap_168332", "taptap_23167"])
    names = [item["name"] for item in payload["items"]]
    assert names == ["原神", "王者荣耀"]
    assert payload["data_source"] == "taptap_public"
    assert all(item["game_id"].startswith("taptap_") for item in payload["items"])

"""Tests for archive sharing and version context matching."""

from __future__ import annotations

from unittest.mock import patch

from src.services.archive_share import build_report_data_from_archive, create_archive_share_link
from src.services.version_context import version_context_for_archive


def test_build_report_data_from_archive_taptap():
    archive = {
        "archive_id": "abc123",
        "title": "竞品分析总结 · 2 款产品",
        "body_markdown": "# 报告",
        "snapshot_json": {
            "platform": "taptap",
            "data_source": "taptap_public",
            "executive_summary": "原神与王者荣耀对比",
            "dimension_scores": [{"game_id": "taptap_168332", "name": "原神", "scores": {"gameplay": 3}}],
            "score_dimensions": [{"key": "gameplay", "title": "核心玩法"}],
            "action_items": [{"priority": "P1", "title": "优化抽卡体验", "owner_role": "策划", "action": "调整", "verify_metric": "好评率"}],
        },
    }
    report = build_report_data_from_archive(archive)
    assert report["data_source"] == "taptap_public"
    assert report["platform"] == "taptap"
    assert report["dimension_scores"][0]["name"] == "原神"
    assert report["action_items"][0]["title"] == "优化抽卡体验"


def test_version_context_matches_delta_by_product_id():
    archive = {
        "game_ids": ["taptap_168332"],
        "created_at": "2026-05-01T10:00:00",
        "snapshot_json": {
            "generated_at": "2026-05-01T10:00:00",
            "last_retest_deltas": [
                {
                    "product_id": "168332",
                    "product_name": "原神",
                    "positive_rate_before": 60.0,
                    "positive_rate_after": 66.7,
                    "delta": 6.7,
                }
            ],
        },
    }
    versions = [
        {
            "version_label": "4.6 更新",
            "released_at": "2026-05-10",
            "change_summary": "新区域开放",
        }
    ]
    with patch("src.services.version_context.GameLibraryRepository.get") as mock_game, patch(
        "src.services.version_context.GameVersionRepository.list_for_game"
    ) as mock_versions:
        mock_game.return_value = {"name": "原神"}
        mock_versions.return_value = versions
        ctx = version_context_for_archive(archive)
    assert ctx["correlations"]


@patch("src.services.archive_share.SharedReportRepository.create_share")
@patch("src.services.archive_share.AnalysisArchiveRepository.get")
@patch("src.services.archive_share.db_manager_update_share_token")
def test_create_archive_share_link(mock_update, mock_get, mock_create):
    mock_get.return_value = {
        "archive_id": "arch1",
        "title": "测试归档",
        "report_type": "ai_competitor",
        "body_markdown": "# hi",
        "snapshot_json": {"platform": "steam", "executive_summary": "摘要"},
    }
    mock_create.return_value = "tok123"
    out = create_archive_share_link("demo", "arch1", base_url="http://localhost:8080")
    assert out["success"] is True
    assert out["share_token"] == "tok123"
    assert "/shared/tok123" in out["share_url"]
    mock_update.assert_called_once()

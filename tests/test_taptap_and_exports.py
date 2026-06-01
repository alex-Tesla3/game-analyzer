"""Tests for TapTap pipeline and export formats."""

from __future__ import annotations

from src.services.action_tasks import (
    actions_to_feishu_markdown,
    actions_to_jira_csv,
    export_actions_content,
)
from src.services.taptap_pipeline import resolve_taptap_inputs, run_taptap_pipeline


def test_resolve_taptap_alias():
    out = resolve_taptap_inputs("原神")
    assert out["success"] is True
    assert out["app_ids"] == ["168332"]


def test_run_taptap_pipeline_offline(tmp_path):
    out_dir = tmp_path / "mvp"
    result = run_taptap_pipeline(["168332"], output_dir=str(out_dir))
    assert result["success"] is True
    assert (out_dir / "taptap_dataset.json").exists()
    assert (out_dir / "steam_dataset.json").exists()


def test_export_feishu_and_jira():
    items = [{"priority": "P0", "title": "Fix MM", "owner_role": "程序", "action": "优化匹配", "verify_metric": "好评率"}]
    feishu, _, ext = export_actions_content(items, "feishu")
    assert "Fix MM" in feishu
    assert ext == "feishu.md"
    jira, _, ext2 = export_actions_content(items, "jira")
    assert "Fix MM" in jira
    assert "Highest" in jira
    assert "jira.csv" in ext2

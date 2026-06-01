"""Tests for Google Play pipeline."""

from __future__ import annotations

from src.services.google_play_pipeline import resolve_google_play_inputs, run_google_play_pipeline


def test_resolve_google_play_alias():
    out = resolve_google_play_inputs("原神")
    assert out["success"] is True
    assert out["app_ids"] == ["com.miHoYo.GenshinImpact"]


def test_resolve_google_play_package():
    out = resolve_google_play_inputs("com.tencent.tmgp.sgame")
    assert out["success"] is True
    assert "com.tencent.tmgp.sgame" in out["app_ids"]


def test_run_google_play_pipeline_offline(tmp_path):
    out_dir = tmp_path / "mvp"
    result = run_google_play_pipeline(["com.miHoYo.GenshinImpact"], output_dir=str(out_dir))
    assert result["success"] is True
    assert (out_dir / "google_play_dataset.json").exists()
    assert (out_dir / "steam_dataset.json").exists()

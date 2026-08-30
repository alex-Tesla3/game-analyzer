"""爬取完成事件自动触发测试。"""

from __future__ import annotations

from src.services.auto_process import auto_process_enabled, maybe_trigger_auto_process


def test_disabled_by_default(monkeypatch):
    monkeypatch.delenv("AUTO_PROCESS_AFTER_CRAWL", raising=False)
    assert auto_process_enabled() is False
    assert maybe_trigger_auto_process("demo", "/tmp/nonexistent") is None


def test_enabled_missing_dataset(monkeypatch):
    monkeypatch.setenv("AUTO_PROCESS_AFTER_CRAWL", "true")
    assert auto_process_enabled() is True
    assert maybe_trigger_auto_process("demo", "/tmp/nonexistent_dir") is None

"""Tests for version context around archives."""

from __future__ import annotations

from src.services.game_versions import GameVersionRepository
from src.services.version_context import version_context_for_archive


def test_version_context_since_baseline():
    archive = {
        "game_ids": ["steam_730"],
        "created_at": "2026-05-01T10:00:00",
        "snapshot_json": {"generated_at": "2026-05-01T10:00:00", "action_items": []},
    }
    from unittest.mock import patch

    versions = [
        {"version_label": "1.2.0", "released_at": "2026-05-15", "change_summary": "Balance patch"},
        {"version_label": "1.0.0", "released_at": "2026-04-01", "change_summary": "Old patch"},
    ]
    with patch.object(GameVersionRepository, "list_for_game", return_value=versions):
        with patch("src.services.version_context.GameLibraryRepository.get", return_value={"name": "CS2"}):
            ctx = version_context_for_archive(archive)
    assert ctx["success"] is True
    assert ctx["total_since_baseline"] == 1
    assert ctx["games"][0]["since_baseline"][0]["version_label"] == "1.2.0"

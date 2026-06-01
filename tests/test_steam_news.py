"""Steam news parsing helpers."""

from __future__ import annotations

from unittest.mock import patch

from src.services.steam_news import _classify_news, fetch_steam_news_items


def test_classify_news_balance():
    assert _classify_news("Balance Update", "nerf assault rifle") == "balance"


def test_fetch_steam_news_items_parses_payload():
    payload = {
        "appnews": {
            "newsitems": [
                {
                    "title": "Patch v1.2.3 — bug fixes",
                    "date": 1717200000,
                    "contents": "<p>Fixed crash on startup</p>",
                    "url": "https://store.steampowered.com/news/1",
                    "gid": "99",
                }
            ]
        }
    }

    class FakeResp:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return payload

    with patch("src.services.steam_news.requests.get", return_value=FakeResp()):
        rows = fetch_steam_news_items("730", count=5)

    assert len(rows) == 1
    assert rows[0]["version_label"].startswith("v1.2.3") or "1.2.3" in rows[0]["version_label"]
    assert rows[0]["source"] == "steam_news"
    assert "Fixed crash" in rows[0]["change_summary"]

"""sitemap.xml and robots.txt tests."""

from __future__ import annotations

from fastapi.testclient import TestClient


def _client() -> TestClient:
    from src.web_app import app

    return TestClient(app)


def test_sitemap_xml_served(monkeypatch):
    monkeypatch.setenv("PUBLIC_DEMO_BASE_URL", "https://game-analyzer-eq8i.onrender.com")
    res = _client().get("/sitemap.xml")
    assert res.status_code == 200
    assert "application/xml" in res.headers["content-type"]
    assert "https://game-analyzer-eq8i.onrender.com/pricing" in res.text
    assert "https://game-analyzer-eq8i.onrender.com/" in res.text
    assert "<urlset" in res.text and "</urlset>" in res.text
    assert "game-analyzer-eq8i.onrender.com/admin" not in res.text


def test_robots_txt_served(monkeypatch):
    monkeypatch.setenv("PUBLIC_DEMO_BASE_URL", "https://game-analyzer-eq8i.onrender.com")
    res = _client().get("/robots.txt")
    assert res.status_code == 200
    assert "Sitemap: https://game-analyzer-eq8i.onrender.com/sitemap.xml" in res.text
    assert "Disallow: /api/" in res.text

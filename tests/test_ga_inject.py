"""Google Analytics gtag.js injection middleware tests."""

from __future__ import annotations

from fastapi.testclient import TestClient


def _client() -> TestClient:
    from src.web_app import app

    return TestClient(app)


def test_landing_page_contains_gtag_snippet(monkeypatch):
    monkeypatch.setenv("GOOGLE_ANALYTICS_ID", "G-70XNK1WHPX")
    res = _client().get("/")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]
    assert 'src="https://www.googletagmanager.com/gtag/js?id=G-70XNK1WHPX"' in res.text
    assert "gtag('config', 'G-70XNK1WHPX');" in res.text
    # snippet is placed inside <head>
    head = res.text.split("</head>")[0]
    assert "googletagmanager.com" in head


def test_api_json_not_injected():
    res = _client().get("/api/health")
    assert res.status_code == 200
    assert "googletagmanager.com" not in res.text


def test_measurement_id_from_env(monkeypatch):
    monkeypatch.setenv("GOOGLE_ANALYTICS_ID", "G-CUSTOM123")
    res = _client().get("/dashboard")
    assert res.status_code == 200
    assert "gtag/js?id=G-CUSTOM123" in res.text
    assert "G-70XNK1WHPX" not in res.text


def test_no_double_injection(monkeypatch):
    monkeypatch.setenv("GOOGLE_ANALYTICS_ID", "G-70XNK1WHPX")
    res = _client().get("/")
    assert res.text.count("googletagmanager.com/gtag/js") == 1

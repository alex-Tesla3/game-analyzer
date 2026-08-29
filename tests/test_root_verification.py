"""Root-level verification file serving (Google Search Console etc.)."""

from __future__ import annotations

from fastapi.testclient import TestClient


def _client() -> TestClient:
    from src.web_app import app

    return TestClient(app)


def test_serves_google_verification_file():
    res = _client().get("/googledc482112bcd317b2.html")
    assert res.status_code == 200
    assert "google-site-verification" in res.text


def test_missing_verification_file_is_404():
    res = _client().get("/googledc0000000000000000.html")
    assert res.status_code == 404


def test_existing_routes_not_shadowed():
    client = _client()
    assert client.get("/api/health").status_code == 200
    assert client.get("/dashboard").status_code == 200
    login = client.get("/login")
    assert login.status_code in (200, 301, 302, 307)

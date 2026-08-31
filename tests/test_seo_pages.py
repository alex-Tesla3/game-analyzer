"""SEO 内容页测试(游戏舆情 AI 分析平台)。"""

from __future__ import annotations

from fastapi.testclient import TestClient

EXPECTED = {
    "/game-public-opinion-ai-analysis": "游戏舆情 AI 分析平台",
    "/ai-game-opinion-monitoring-system": "AI 游戏舆情监测系统",
    "/game-negative-public-opinion-monitoring": "负面舆情风险识别",
    "/mobile-game-player-experience-analysis": "玩家体验舆情分析",
    "/game-hot-event-tracking": "热点事件追踪",
    "/game-monetization-controversy-monitoring": "商业化争议舆情监测",
    "/cross-platform-game-opinion-aggregation": "跨平台舆情聚合",
}


def _client() -> TestClient:
    from src.web_app import app

    return TestClient(app)


def test_seo_pages_serve_with_meta():
    c = _client()
    for path, title_kw in EXPECTED.items():
        res = c.get(path)
        assert res.status_code == 200, f"{path} -> {res.status_code}"
        assert "text/html" in res.headers["content-type"]
        assert title_kw in res.text
        assert '<meta name="description"' in res.text
        assert '<meta name="keywords"' in res.text
        assert 'rel="canonical"' in res.text


def test_seo_pages_cross_link_and_boundary():
    c = _client()
    res = c.get("/game-public-opinion-ai-analysis")
    # 站内互链
    assert "/ai-game-opinion-monitoring-system" in res.text
    assert "/game-negative-public-opinion-monitoring" in res.text
    # 数据边界标注
    assert "数据边界" in res.text
    assert "不编造内容" in res.text


def test_sitemap_includes_seo_pages(monkeypatch):
    monkeypatch.setenv("PUBLIC_DEMO_BASE_URL", "https://game-analyzer-eq8i.onrender.com")
    res = _client().get("/sitemap.xml")
    assert res.status_code == 200
    for path in EXPECTED:
        assert f"https://game-analyzer-eq8i.onrender.com{path}" in res.text


def test_unknown_seo_path_404():
    res = _client().get("/game-public-opinion-ai-analysis-unknown")
    assert res.status_code == 404


def test_no_nexus_branding():
    c = _client()
    for path in EXPECTED:
        html = c.get(path).text
        assert "NEXUS" not in html, f"{path} 仍含 NEXUS 标志"


def test_topbar_links_use_urls_not_labels():
    html = _client().get("/game-negative-public-opinion-monitoring").text
    # href 必须是 URL, 文字是标签
    assert 'href="/game-public-opinion-ai-analysis">平台首页' in html
    assert 'href="/ai-game-opinion-monitoring-system">AI 监测系统' in html
    assert 'href="平台首页"' not in html


def test_next_steps_causal_path_present():
    html = _client().get("/game-negative-public-opinion-monitoring").text
    assert "下一步 · 推荐路径" in html
    assert "了解 AI 监测系统" in html
    assert "回到平台总览" in html
    assert "查看负面预警" in html


def test_hub_page_lists_five_scenarios():
    html = _client().get("/game-public-opinion-ai-analysis").text
    assert "5 大能力场景" in html
    assert "/game-negative-public-opinion-monitoring" in html
    assert "/cross-platform-game-opinion-aggregation" in html

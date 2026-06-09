/**
 * 帮助与指引侧栏 — 数据流 + 分析场景（不重复顶部主导航）
 */
(function (global) {
    "use strict";

    function esc(s) {
        const d = document.createElement("div");
        d.textContent = s || "";
        return d.innerHTML;
    }

    function dataFlowSteps() {
        const copy = global.DataFlowGuide && global.DataFlowGuide.COPY;
        if (!copy || !copy.steps) return [];
        return copy.steps;
    }

    function guideScenarios() {
        const guides = global.AnalysisGuide && global.AnalysisGuide.GUIDES;
        if (!guides) return [];
        return Object.keys(guides).map((key) => ({ key, ...guides[key] }));
    }

    function headerOffsetPx() {
        const header = document.querySelector(".sidebar, .topbar, .landing-topbar, .nav-slot");
        return header ? header.getBoundingClientRect().height : 0;
    }

    function applyHeaderOffset() {
        const px = headerOffsetPx();
        document.documentElement.style.setProperty("--smp-header-offset", px ? px + "px" : "0px");
    }

    function hasTopNavigation() {
        return !!document.querySelector(".app-nav, #app-nav-mount .app-nav");
    }

    function renderNavHint() {
        if (!hasTopNavigation()) return "";
        return (
            '<p class="smp-nav-hint">' +
            "页面跳转请使用<strong>顶部导航栏</strong>（首页 · 向导 · 看板 · 更多）。" +
            "本侧栏仅说明<strong>数据流</strong>与<strong>分析步骤</strong>，不重复站点地图。" +
            "</p>"
        );
    }

    function renderDataFlow() {
        const steps = dataFlowSteps();
        if (!steps.length) return "";
        return (
            '<section class="smp-section">' +
            '<h3 class="smp-section-title">📡 数据流</h3>' +
            '<p class="smp-hint">抓取与看板共用 <code>data/mvp/</code>，无需单独导入。</p>' +
            '<ol class="smp-flow">' +
            steps
                .map(
                    (s) =>
                        '<li><span class="smp-flow-num">' +
                        esc(s.num) +
                        '</span><div><strong>' +
                        esc(s.title) +
                        "</strong><p>" +
                        esc(s.body) +
                        "</p>" +
                        (s.links && s.links.length
                            ? '<span class="smp-mini-links">' +
                              s.links
                                  .map((l) => '<a href="' + esc(l.href) + '">' + esc(l.label) + "</a>")
                                  .join(" · ") +
                              "</span>"
                            : "") +
                        "</div></li>"
                )
                .join("") +
            "</ol></section>"
        );
    }

    function renderGuides() {
        const scenarios = guideScenarios();
        if (!scenarios.length) return "";
        return (
            '<section class="smp-section">' +
            '<h3 class="smp-section-title">📐 分析场景</h3>' +
            '<div class="smp-guides">' +
            scenarios
                .map((g) => {
                    const steps =
                        g.steps && g.steps.length
                            ? '<ol class="smp-guide-steps">' +
                              g.steps
                                  .slice(0, 4)
                                  .map((s) => "<li>" + esc(s) + "</li>")
                                  .join("") +
                              (g.steps.length > 4 ? '<li class="smp-more">…共 ' + g.steps.length + " 步</li>" : "") +
                              "</ol>"
                            : "";
                    return (
                        '<details class="smp-guide-item">' +
                        '<summary><span class="smp-guide-icon">' +
                        g.icon +
                        "</span><span>" +
                        esc(g.title) +
                        '</span><a class="smp-guide-go" href="' +
                        esc(g.href) +
                        '">前往 →</a></summary>' +
                        '<p class="smp-guide-sub">' +
                        esc(g.subtitle) +
                        "</p>" +
                        steps +
                        (g.tips ? '<p class="smp-guide-tip">💡 ' + esc(g.tips) + "</p>" : "") +
                        "</details>"
                    );
                })
                .join("") +
            "</div></section>"
        );
    }

    function renderFab() {
        if (hasTopNavigation()) return "";
        return (
            '<button type="button" class="smp-fab" id="smp-fab" aria-label="打开帮助与指引" title="帮助与指引">' +
            '<span class="smp-fab-icon">📖</span><span class="smp-fab-label">指引</span>' +
            "</button>"
        );
    }

    function renderPanel() {
        return (
            '<div class="smp-overlay" id="smp-overlay" aria-hidden="true"></div>' +
            '<aside class="smp-panel" id="smp-panel" role="dialog" aria-label="帮助与指引" aria-hidden="true">' +
            '<header class="smp-header">' +
            '<div><h2 class="smp-title">📖 帮助与指引</h2>' +
            '<p class="smp-subtitle">数据流说明 · 分析场景步骤</p></div>' +
            '<button type="button" class="smp-close" id="smp-close" aria-label="关闭">×</button>' +
            "</header>" +
            '<div class="smp-body">' +
            renderNavHint() +
            renderDataFlow() +
            renderGuides() +
            '<p class="smp-footer"><a href="/trust">数据可信度</a> · <a href="/showcase">作品集</a></p>' +
            "</div></aside>" +
            renderFab()
        );
    }

    let mounted = false;

    function bindEvents() {
        const overlay = document.getElementById("smp-overlay");
        const panel = document.getElementById("smp-panel");
        const fab = document.getElementById("smp-fab");
        const closeBtn = document.getElementById("smp-close");
        if (!overlay || !panel) return;

        fab?.addEventListener("click", () => toggle(true));
        closeBtn?.addEventListener("click", () => toggle(false));
        overlay.addEventListener("click", () => toggle(false));

        document.addEventListener("keydown", (e) => {
            if (e.key === "Escape" && panel.classList.contains("smp-open")) toggle(false);
        });

        document.addEventListener("click", (e) => {
            const btn = e.target.closest("[data-sitemap-open]");
            if (btn) {
                e.preventDefault();
                toggle(true);
            }
        });

        panel.querySelectorAll("a.smp-guide-go, .smp-mini-links a, .smp-footer a").forEach((a) => {
            a.addEventListener("click", (e) => {
                e.stopPropagation();
                toggle(false);
            });
        });

        window.addEventListener("resize", applyHeaderOffset);
    }

    function toggle(open) {
        const overlay = document.getElementById("smp-overlay");
        const panel = document.getElementById("smp-panel");
        const fab = document.getElementById("smp-fab");
        if (!overlay || !panel) return;

        refreshPanelChrome();
        const next = typeof open === "boolean" ? open : !panel.classList.contains("smp-open");
        panel.classList.toggle("smp-open", next);
        overlay.classList.toggle("smp-open", next);
        fab?.classList.toggle("smp-fab-hidden", next);
        panel.setAttribute("aria-hidden", next ? "false" : "true");
        overlay.setAttribute("aria-hidden", next ? "false" : "true");
        document.body.classList.toggle("smp-no-scroll", next);

        if (!next && (location.hash === "#sitemap" || location.hash === "#analysis-guide")) {
            history.replaceState(null, "", location.pathname + location.search);
        }
    }

    function refreshPanelChrome() {
        applyHeaderOffset();
        const body = document.querySelector("#smp-panel .smp-body");
        if (body && hasTopNavigation() && !body.querySelector(".smp-nav-hint")) {
            body.insertAdjacentHTML("afterbegin", renderNavHint());
        }
        const fab = document.getElementById("smp-fab");
        if (hasTopNavigation() && fab) fab.remove();
    }

    function mount() {
        if (mounted || document.getElementById("smp-panel")) return;
        applyHeaderOffset();
        const root = document.createElement("div");
        root.id = "smp-root";
        root.innerHTML = renderPanel();
        document.body.appendChild(root);
        bindEvents();
        mounted = true;
        setTimeout(refreshPanelChrome, 60);

        const hash = (location.hash || "").replace("#", "");
        if (hash === "sitemap" || hash === "analysis-guide") {
            setTimeout(() => toggle(true), 120);
        }
    }

    function open() {
        if (!mounted) mount();
        toggle(true);
    }

    function close() {
        toggle(false);
    }

    global.SiteMapPanel = { mount, open, close, toggle };

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", mount);
    } else {
        mount();
    }
})(typeof window !== "undefined" ? window : globalThis);

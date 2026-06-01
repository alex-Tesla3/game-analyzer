/** Unified top navigation — primary items +「更多」dropdown */
(function (global) {
    var PRIMARY = [
        { id: "home", label: "首页", href: "/", icon: "🏠", home: true },
        { id: "guide", label: "分析向导", href: "/guide", icon: "🧭" },
        { id: "dashboard", label: "数据看板", href: "/dashboard", icon: "📊" },
        { id: "compare", label: "竞品分析", href: "/games/compare", icon: "⚔️" },
        { id: "review", label: "复盘归档", href: "/games/review", icon: "📅" },
    ];

    var MORE = [
        { id: "work", label: "落地指导", href: "/work" },
        { id: "library", label: "资料库", href: "/games/library" },
        { id: "comments", label: "评论分析", href: "/comments" },
        { id: "metrics", label: "指标详情", href: "/metrics" },
        { id: "import", label: "导入指标", href: "/import" },
        { id: "mvp", label: "真实竞品", href: "/mvp" },
        { id: "team", label: "团队协作", href: "/team" },
        { divider: true },
        { id: "guide-panel", label: "分析指引", href: "/dashboard#analysis-guide" },
        { id: "pricing", label: "订阅套餐", href: "/pricing" },
    ];

    function esc(s) {
        var d = document.createElement("div");
        d.textContent = s || "";
        return d.innerHTML;
    }

    function detectActive(fallback) {
        var path = location.pathname.replace(/\/$/, "") || "/";
        if (path === "/" || path === "/welcome") return "home";
        if (path === "/dashboard") return "dashboard";
        if (path.indexOf("/guide") === 0) return "guide";
        if (path.indexOf("/games/compare") === 0) return "compare";
        if (path.indexOf("/games/review") === 0) return "review";
        if (path.indexOf("/work") === 0) return "work";
        if (path.indexOf("/games/library") === 0) return "library";
        if (path.indexOf("/comments") === 0) return "comments";
        if (path.indexOf("/metrics") === 0) return "metrics";
        if (path.indexOf("/import") === 0) return "import";
        if (path.indexOf("/mvp") === 0) return "mvp";
        if (path.indexOf("/team") === 0) return "team";
        if (path.indexOf("/pricing") === 0) return "pricing";
        return fallback || "";
    }

    function render(activeId) {
        var primaryHtml = PRIMARY.map(function (item) {
            var cls = "app-nav-item" + (item.id === activeId ? " active" : "");
            if (item.home) cls += " app-nav-home";
            return (
                '<a class="' +
                cls +
                '" href="' +
                esc(item.href) +
                '"><span class="app-nav-icon">' +
                item.icon +
                '</span><span class="app-nav-label">' +
                esc(item.label) +
                "</span></a>"
            );
        }).join("");

        var moreActive = MORE.some(function (m) {
            return m.id === activeId;
        });
        var moreItems = MORE.map(function (item) {
            if (item.divider) return '<div class="app-nav-divider"></div>';
            var cls = item.id === activeId ? ' class="active"' : "";
            return '<a href="' + esc(item.href) + '"' + cls + ">" + esc(item.label) + "</a>";
        }).join("");

        return (
            '<nav class="app-nav" role="navigation" aria-label="主导航">' +
            primaryHtml +
            '<div class="app-nav-more' +
            (moreActive ? " open" : "") +
            '">' +
            '<button type="button" class="app-nav-item' +
            (moreActive ? " active" : "") +
            '" id="app-nav-more-btn" aria-haspopup="true" aria-expanded="' +
            (moreActive ? "true" : "false") +
            '"><span class="app-nav-icon">⋯</span><span class="app-nav-label">更多</span></button>' +
            '<div class="app-nav-dropdown" id="app-nav-dropdown">' +
            moreItems +
            "</div></div></nav>"
        );
    }

    function bindDropdown(root) {
        var wrap = root.querySelector(".app-nav-more");
        var btn = root.querySelector("#app-nav-more-btn");
        var menu = root.querySelector("#app-nav-dropdown");
        if (!wrap || !btn || !menu) return;

        btn.addEventListener("click", function (e) {
            e.stopPropagation();
            var open = wrap.classList.toggle("open");
            btn.setAttribute("aria-expanded", open ? "true" : "false");
        });

        document.addEventListener("click", function () {
            wrap.classList.remove("open");
            btn.setAttribute("aria-expanded", "false");
        });

        menu.addEventListener("click", function (e) {
            e.stopPropagation();
        });
    }

    function mount(selector, opts) {
        opts = opts || {};
        var el = typeof selector === "string" ? document.querySelector(selector) : selector;
        if (!el) return;
        var active = opts.active || el.getAttribute("data-active") || detectActive();
        el.innerHTML = render(active);
        bindDropdown(el);
    }

    global.AppNav = { mount: mount, detectActive: detectActive, PRIMARY: PRIMARY, MORE: MORE };
})(typeof window !== "undefined" ? window : globalThis);

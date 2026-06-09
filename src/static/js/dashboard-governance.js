/** Dashboard data governance: de-emphasize mock KPIs; flag simulated advanced analytics. */
(function (global) {
    function apply(payload) {
        if (!payload) return;
        global.dataProvenance = payload;
        const source = payload.source || "";
        const isMock = source === "mock";
        const isReal =
            source === "imported" ||
            source === "mvp_steam" ||
            source === "mvp_multi" ||
            source === "taptap_public" ||
            source === "google_play_public" ||
            (source && source.startsWith("mvp_"));

        global.__gaSimulatedAnalytics = isMock || !!payload.collapse_demo_metrics;

        const kpiGrid = document.getElementById("kpi-grid");
        if (kpiGrid) {
            kpiGrid.classList.toggle("demo-metrics", isMock);
            kpiGrid.classList.toggle("steam-trust-kpi", isReal);
        }

        const advBtn = document.querySelector('[onclick*="openAdvancedAnalysis"]');
        if (advBtn && isMock) {
            advBtn.setAttribute("title", "高级分析为演示曲线，请优先使用 Steam 口碑与竞品工作台");
        }
    }

    function injectAdvancedWarning() {
        if (!global.__gaSimulatedAnalytics) return;
        const modal = document.getElementById("advanced-analysis-section");
        if (!modal || document.getElementById("sim-adv-inline-banner")) return;
        const banner = document.createElement("div");
        banner.id = "sim-adv-inline-banner";
        banner.className = "simulated-analytics-banner";
        banner.innerHTML =
            '<div class="sim-banner-inner">' +
            "<strong>⚠️ 演示数据</strong>" +
            "<span>本面板留存/漏斗/实时曲线为模型演示，不可直接用于 Steam 竞品结论。请优先使用<strong> Steam 口碑 KPI</strong>与<strong>竞品工作台</strong>。</span>" +
            "</div>";
        const header = modal.querySelector(".modal-header");
        if (header && header.nextSibling) {
            modal.insertBefore(banner, header.nextSibling);
        } else {
            modal.prepend(banner);
        }
    }

    global.DashboardGovernance = { apply, injectAdvancedWarning };
})(typeof window !== "undefined" ? window : globalThis);

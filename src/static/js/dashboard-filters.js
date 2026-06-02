/**
 * Dashboard filter catalog, metrics fetch, and view pipeline.
 * Loaded before the main dashboard script in index.html.
 */
(function (global) {
    "use strict";

    global.selectedProducts = global.selectedProducts || ["game_a", "game_b", "game_c"];
    global.currentMetricsData = global.currentMetricsData || [];
    global.allMetricsData = global.allMetricsData ?? null;
    global.metricsLoadPromise = global.metricsLoadPromise ?? null;
    global.currentTimePeriod = global.currentTimePeriod || "week_22";
    global.currentDataSource = global.currentDataSource || "all";
    global.currentGenre = global.currentGenre || "all";
    global.productGenreMap = global.productGenreMap || {};
    global.allProductsCatalog = global.allProductsCatalog || [];
    global.productNamesMap = global.productNamesMap || {
        game_a: "游戏A - 战神传说",
        game_b: "游戏B - 星际争霸",
        game_c: "游戏C - 魔法大陆",
    };
    global.timePeriodLabels = global.timePeriodLabels || {
        week_20: "第20周",
        week_21: "第21周",
        week_22: "第22周",
        quarter_2: "Q2季度",
    };

    function debounce(func, wait) {
        let timeout;
        return function debounced(...args) {
            clearTimeout(timeout);
            timeout = setTimeout(() => func.apply(this, args), wait);
        };
    }

    function normalizeCatalogProductId(value) {
        const pid = String(value || "").trim();
        if (pid.startsWith("steam_") && /^\d+$/.test(pid.slice(6))) {
            return pid.slice(6);
        }
        return pid;
    }

    function metricMatchesPeriod(metric, period) {
        if (!period || period === "all") return true;
        const cycleRaw = String(metric.cycle || metric.周期 || "").trim();
        if (!cycleRaw) return true;
        if (cycleRaw === period || cycleRaw.toLowerCase() === String(period).toLowerCase()) {
            return true;
        }
        const normalizeKey = (text) =>
            String(text || "")
                .toLowerCase()
                .replace(/_/g, " ")
                .replace(/-/g, " ")
                .trim();
        const aliases = {
            "week 20": "week_20",
            week20: "week_20",
            "week 21": "week_21",
            week21: "week_21",
            "week 22": "week_22",
            week22: "week_22",
            q2: "q2",
            "quarter 2": "q2",
            quarter2: "q2",
        };
        const normalized = aliases[normalizeKey(period)] || String(period).toLowerCase();
        const cycleKey = normalizeKey(cycleRaw);
        const cycleCompact = cycleKey.replace(/\s+/g, "");
        const candidates = new Set([normalized, String(period).toLowerCase()]);
        if (normalized === "week_20") {
            candidates.add("week 20");
            candidates.add("week20");
        } else if (normalized === "week_21") {
            candidates.add("week 21");
            candidates.add("week21");
        } else if (normalized === "week_22") {
            candidates.add("week 22");
            candidates.add("week22");
        } else if (normalized === "q2") {
            candidates.add("q2");
            candidates.add("quarter 2");
            candidates.add("quarter_2");
        } else if (normalized.startsWith("month_")) {
            candidates.add(normalized.replace("_", " "));
        }
        for (const candidate of candidates) {
            if (!candidate) continue;
            const cand = normalizeKey(candidate);
            const candCompact = cand.replace(/\s+/g, "");
            if (cycleKey === cand || cycleCompact === candCompact) return true;
            if (cycleKey.includes(cand) || cycleCompact.includes(candCompact)) return true;
        }
        const dateValue = String(metric.date || metric.日期 || "");
        return dateValue.startsWith(String(period).slice(0, 4));
    }

    function productRecordMatches(metric, productId) {
        const pid = normalizeCatalogProductId(productId);
        const displayName = global.productNamesMap[productId] || global.productNamesMap[pid] || pid;
        return (
            normalizeCatalogProductId(metric.product || metric.产品 || metric.app_id || "") === pid ||
            metric.product === displayName ||
            String(metric.product_name || "") === displayName
        );
    }

    function syncFiltersFromDom() {
        const productSelect = document.getElementById("product-select");
        const periodSelect = document.getElementById("time-period-select");
        const sourceSelect = document.getElementById("data-source-select");
        const genreSelect = document.getElementById("genre-select");
        if (productSelect) {
            global.selectedProducts = Array.from(productSelect.selectedOptions).map((o) => o.value);
            if (global.selectedProducts.length === 0) {
                global.selectedProducts = Array.from(productSelect.options).map((o) => o.value);
            }
        }
        if (periodSelect) global.currentTimePeriod = periodSelect.value;
        if (sourceSelect) global.currentDataSource = sourceSelect.value;
        if (genreSelect) global.currentGenre = genreSelect.value;
    }

    function productsMatchingGenre(products, genre) {
        if (!Array.isArray(products)) return [];
        if (!genre || genre === "all") return products;
        return products.filter((p) => {
            const g = p.genre || global.productGenreMap[p.id] || "PC Game";
            return g === genre;
        });
    }

    const DEMO_DEFAULT_PRODUCT_IDS = ["730", "570"];

    function defaultProductIdsForList(list) {
        const demo = DEMO_DEFAULT_PRODUCT_IDS.filter((id) => list.some((p) => p.id === id));
        if (demo.length) return demo;
        return list.slice(0, 2).map((p) => p.id);
    }

    function fillProductSelect(selectEl, products, options) {
        options = options || {};
        if (!selectEl || !Array.isArray(products) || !products.length) return;
        const selectedIds =
            options.selectedIds instanceof Set ? options.selectedIds : new Set(options.selectedIds || []);
        const defaultCount = options.defaultCount ?? 2;
        selectEl.innerHTML = "";
        products.forEach((item, index) => {
            global.productNamesMap[item.id] = item.name || item.id;
            const option = document.createElement("option");
            option.value = item.id;
            option.textContent = item.name || item.id;
            option.selected = selectedIds.size
                ? selectedIds.has(item.id)
                : index < Math.min(defaultCount, products.length);
            selectEl.appendChild(option);
        });
    }

    function applyGenreToProductSelect() {
        const productSelect = document.getElementById("product-select");
        if (!productSelect || !global.allProductsCatalog.length) return;

        const genre = document.getElementById("genre-select")?.value || global.currentGenre || "all";
        global.currentGenre = genre;
        const filtered = productsMatchingGenre(global.allProductsCatalog, genre);

        if (genre !== "all" && !filtered.length) {
            productSelect.innerHTML = '<option disabled selected>该品类暂无产品数据</option>';
            global.selectedProducts = [];
            if (typeof global.syncReportProductOptions === "function") {
                global.syncReportProductOptions(global.allProductsCatalog);
            }
            if (typeof global.renderProductList === "function") global.renderProductList();
            return;
        }

        const list = filtered.length ? filtered : global.allProductsCatalog;
        const selectAllInGenre = genre !== "all";
        fillProductSelect(productSelect, list, {
            selectedIds: selectAllInGenre
                ? new Set(list.map((p) => p.id))
                : new Set(
                      global.selectedProducts.length
                          ? global.selectedProducts
                          : defaultProductIdsForList(list)
                  ),
            defaultCount: selectAllInGenre ? list.length : 2,
        });
        global.selectedProducts = Array.from(productSelect.selectedOptions).map((o) => o.value);
        if (typeof global.syncReportProductOptions === "function") {
            global.syncReportProductOptions(list);
        }
        if (typeof global.renderProductList === "function") global.renderProductList();
    }

    function getSelectedProductIds() {
        const productSelect = document.getElementById("product-select");
        if (!productSelect) return global.selectedProducts.slice();
        const picked = Array.from(productSelect.selectedOptions).map((o) => o.value);
        return picked.length ? picked : Array.from(productSelect.options).map((o) => o.value);
    }

    function setDashboardLoading(loading) {
        const el = document.getElementById("dashboard-loading");
        const btn = document.getElementById("apply-filters-btn");
        if (el) el.style.display = loading ? "inline" : "none";
        if (btn) btn.disabled = !!loading;
    }

    async function fetchMetricsWithFilters() {
        const checkAuth = global.checkAuth || (() => !!global.getToken?.());
        if (!checkAuth()) return null;
        syncFiltersFromDom();
        const token = global.getToken();
        const params = new URLSearchParams();
        params.set("token", token);
        const productIds = getSelectedProductIds();
        if (productIds.length) params.set("product_ids", productIds.join(","));
        if (global.currentTimePeriod && global.currentTimePeriod !== "all") {
            params.set("time_period", global.currentTimePeriod);
        }
        if (global.currentDataSource && global.currentDataSource !== "all") {
            params.set("data_source", global.currentDataSource);
        }
        const response = await fetch(`/api/metrics?${params.toString()}`);
        if (response.status === 401) {
            if (typeof global.clearAuthToken === "function") global.clearAuthToken();
            else localStorage.removeItem("access_token");
            window.location.href = "/login";
            return null;
        }
        const result = await response.json();
        if (!result.success) {
            throw new Error(result.message || result.detail || "指标加载失败");
        }
        global.allMetricsData = result.data || [];
        global.currentMetricsData = global.allMetricsData;
        return global.currentMetricsData;
    }

    async function ensureMetricsLoaded(forceRefresh) {
        const checkAuth = global.checkAuth || (() => !!global.getToken?.());
        if (!checkAuth()) return null;
        if (!forceRefresh && global.allMetricsData !== null) return global.allMetricsData;
        if (!forceRefresh && global.metricsLoadPromise) return global.metricsLoadPromise;

        setDashboardLoading(true);
        global.metricsLoadPromise = (async () => {
            try {
                return await fetchMetricsWithFilters();
            } catch (e) {
                console.error("指标加载失败", e);
                return global.allMetricsData;
            } finally {
                setDashboardLoading(false);
                global.metricsLoadPromise = null;
            }
        })();
        return global.metricsLoadPromise;
    }

    function getViewMetrics() {
        syncFiltersFromDom();
        let rows = Array.isArray(global.currentMetricsData) ? global.currentMetricsData.slice() : [];
        if (global.currentGenre && global.currentGenre !== "all") {
            rows = rows.filter((m) => {
                const pid = normalizeCatalogProductId(m.product || m.产品);
                return global.productGenreMap[pid] === global.currentGenre;
            });
        }
        return rows;
    }

    function renderDashboard() {
        const viewMetrics = getViewMetrics();
        if (typeof global.updateKPICards === "function") global.updateKPICards(viewMetrics);
        if (typeof global.updateProductCompare === "function") global.updateProductCompare(viewMetrics);
        if (typeof global.updateAlerts === "function") global.updateAlerts(viewMetrics);
        if (typeof global.updatePlatformRankings === "function") global.updatePlatformRankings(viewMetrics);
        if (typeof global.initChart === "function") global.initChart(viewMetrics);
    }

    async function loadFilterOptions() {
        const token = global.getToken?.();
        if (!token) return false;
        try {
            const response = await fetch(`/api/options?token=${encodeURIComponent(token)}`);
            if (response.status === 401) {
                if (typeof global.clearAuthToken === "function") global.clearAuthToken();
                else localStorage.removeItem("access_token");
                window.location.href = "/login?redirect=%2Fdashboard";
                return false;
            }
            if (!response.ok) {
                console.error("加载筛选选项失败", response.status, await response.text());
                return false;
            }
            const result = await response.json();
            if (!result.success) return false;

            const productSelect = document.getElementById("product-select");
            const periodSelect = document.getElementById("time-period-select");

            if (productSelect && Array.isArray(result.products) && result.products.length) {
                global.allProductsCatalog = result.products;
                global.productGenreMap = {};
                result.products.forEach((p) => {
                    if (p.genre) global.productGenreMap[p.id] = p.genre;
                });
            }

            const genreSelect = document.getElementById("genre-select");
            if (genreSelect && Array.isArray(result.genres) && result.genres.length) {
                const prev = genreSelect.value || "all";
                genreSelect.innerHTML = '<option value="all">全部品类</option>';
                result.genres.forEach((g) => {
                    const opt = document.createElement("option");
                    opt.value = g.id || g.name;
                    opt.textContent = g.name || g.id;
                    genreSelect.appendChild(opt);
                });
                genreSelect.value = [...genreSelect.options].some((o) => o.value === prev) ? prev : "all";
                global.currentGenre = genreSelect.value;
            }

            applyGenreToProductSelect();

            if (global.DataProvenance && result.data_trust) {
                const prov = {
                    source: result.data_source,
                    trust: result.data_trust,
                    show_mock_warning: result.data_source === "mock",
                    collapse_demo_metrics: result.data_source === "mvp_steam" || result.data_source === "imported",
                };
                global.DataProvenance.renderBanner("data-provenance-banner", prov);
                if (global.DashboardGovernance) global.DashboardGovernance.apply(prov);
            }

            if (periodSelect && Array.isArray(result.time_periods) && result.time_periods.length) {
                periodSelect.innerHTML = "";
                result.time_periods.forEach((item, index) => {
                    global.timePeriodLabels[item.id] = item.name || item.id;
                    const option = document.createElement("option");
                    option.value = item.id;
                    option.textContent = item.name || item.id;
                    option.selected = index === result.time_periods.length - 1;
                    periodSelect.appendChild(option);
                });
            }

            if (typeof global.syncReportProductOptions === "function") {
                global.syncReportProductOptions(result.products);
            }
            syncFiltersFromDom();
            if (typeof global.renderProductList === "function") global.renderProductList();
            return true;
        } catch (e) {
            console.error("加载筛选选项失败", e);
            return false;
        }
    }

    async function loadData(forceRefresh) {
        const checkAuth = global.checkAuth || (() => !!global.getToken?.());
        if (!checkAuth()) return;
        try {
            await ensureMetricsLoaded(!!forceRefresh);
            renderDashboard();
        } catch (e) {
            console.error("加载失败", e);
        }
    }

    function onFilterChange() {
        const genreSelect = document.getElementById("genre-select");
        if (genreSelect && global.allProductsCatalog.length) {
            applyGenreToProductSelect();
        }
        global.debouncedApplyFilters();
    }

    function applyFilters() {
        syncFiltersFromDom();
        loadData(true);
    }

    function resetFilters() {
        const productSelect = document.getElementById("product-select");
        if (productSelect) {
            Array.from(productSelect.options).forEach((o) => {
                o.selected = true;
            });
        }
        const periodSelect = document.getElementById("time-period-select");
        if (periodSelect && periodSelect.options.length) {
            periodSelect.selectedIndex = periodSelect.options.length - 1;
        }
        const sourceSelect = document.getElementById("data-source-select");
        if (sourceSelect) sourceSelect.value = "all";
        const genreSelect = document.getElementById("genre-select");
        if (genreSelect) {
            genreSelect.value = "all";
            global.currentGenre = "all";
        }
        if (global.allProductsCatalog.length) {
            applyGenreToProductSelect();
        }
        syncFiltersFromDom();
        loadData(true);
    }

    function filterMetricsForView(metrics) {
        if (!Array.isArray(metrics)) return [];
        let rows = metrics.slice();
        if (global.selectedProducts && global.selectedProducts.length) {
            rows = rows.filter((m) => global.selectedProducts.some((pid) => productRecordMatches(m, pid)));
        }
        if (global.currentGenre && global.currentGenre !== "all") {
            rows = rows.filter((m) => {
                const pid = m.product || m.产品;
                return global.productGenreMap[pid] === global.currentGenre;
            });
        }
        if (global.currentTimePeriod && global.currentTimePeriod !== "all") {
            rows = rows.filter((m) => metricMatchesPeriod(m, global.currentTimePeriod));
        }
        if (global.currentDataSource && global.currentDataSource !== "all") {
            const src = global.currentDataSource.replace(/_/g, " ").toLowerCase();
            rows = rows.filter((m) => {
                const ch = String(m.channel || m.platform || m.平台 || "").toLowerCase();
                return ch === src || ch.replace(/\s+/g, " ") === src;
            });
        }
        return rows;
    }

    function filterMetricsByPeriodAndSource(metrics) {
        if (!Array.isArray(metrics)) return [];
        let rows = metrics.slice();
        if (global.currentTimePeriod && global.currentTimePeriod !== "all") {
            rows = rows.filter((m) => metricMatchesPeriod(m, global.currentTimePeriod));
        }
        if (global.currentDataSource && global.currentDataSource !== "all") {
            const src = global.currentDataSource.replace(/_/g, " ").toLowerCase();
            rows = rows.filter((m) => {
                const ch = String(m.channel || m.platform || m.平台 || "").toLowerCase();
                return ch === src || ch.replace(/\s+/g, " ") === src;
            });
        }
        return rows;
    }

    function filterMetricsByGenre(metrics) {
        if (!Array.isArray(metrics)) return [];
        if (!global.currentGenre || global.currentGenre === "all") return metrics;
        return metrics.filter((m) => global.productGenreMap[m.product] === global.currentGenre);
    }

    global.filterMetricsByPeriodAndSource = filterMetricsByPeriodAndSource;
    global.filterMetricsByGenre = filterMetricsByGenre;

    global.debouncedApplyFilters = debounce(() => loadData(false), 250);

    global.normalizeCatalogProductId = normalizeCatalogProductId;
    global.metricMatchesPeriod = metricMatchesPeriod;
    global.productRecordMatches = productRecordMatches;
    global.syncFiltersFromDom = syncFiltersFromDom;
    global.applyGenreToProductSelect = applyGenreToProductSelect;
    global.getSelectedProductIds = getSelectedProductIds;
    global.fillProductSelect = fillProductSelect;
    global.loadFilterOptions = loadFilterOptions;
    global.fetchMetricsWithFilters = fetchMetricsWithFilters;
    global.ensureMetricsLoaded = ensureMetricsLoaded;
    global.getViewMetrics = getViewMetrics;
    global.renderDashboard = renderDashboard;
    global.onFilterChange = onFilterChange;
    global.applyFilters = applyFilters;
    global.resetFilters = resetFilters;
    global.loadData = loadData;
    global.filterMetricsForView = filterMetricsForView;
    global.setDashboardLoading = setDashboardLoading;

    global.DashboardFilters = {
        loadFilterOptions,
        applyFilters,
        loadData,
        getViewMetrics,
        renderDashboard,
        metricMatchesPeriod,
        productRecordMatches,
    };
})(typeof window !== "undefined" ? window : globalThis);

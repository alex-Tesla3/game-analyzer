/** Named dashboard filter views (local persistence). */
(function (global) {
    "use strict";

    const STORAGE_KEY = "ga_dashboard_filter_views_v1";
    const MAX_VIEWS = 12;

    function readAll() {
        try {
            const raw = localStorage.getItem(STORAGE_KEY);
            const list = raw ? JSON.parse(raw) : [];
            return Array.isArray(list) ? list : [];
        } catch {
            return [];
        }
    }

    function writeAll(list) {
        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(list.slice(0, MAX_VIEWS)));
        } catch (_) {
            /* ignore */
        }
    }

    function captureCurrent() {
        if (typeof global.syncFiltersFromDom === "function") {
            global.syncFiltersFromDom();
        }
        const productSelect = document.getElementById("product-select");
        const products = productSelect
            ? Array.from(productSelect.selectedOptions).map((o) => o.value)
            : global.selectedProducts || [];
        return {
            products,
            time_period: global.currentTimePeriod || document.getElementById("time-period-select")?.value || "all",
            data_source: global.currentDataSource || document.getElementById("data-source-select")?.value || "all",
            genre: global.currentGenre || document.getElementById("genre-select")?.value || "all",
        };
    }

    function applyView(view) {
        if (!view) return;
        const productSelect = document.getElementById("product-select");
        const periodSelect = document.getElementById("time-period-select");
        const sourceSelect = document.getElementById("data-source-select");
        const genreSelect = document.getElementById("genre-select");

        if (genreSelect && view.genre) {
            genreSelect.value = view.genre;
            global.currentGenre = view.genre;
            if (typeof global.applyGenreToProductSelect === "function") {
                global.applyGenreToProductSelect();
            }
        }
        if (productSelect && Array.isArray(view.products)) {
            const set = new Set(view.products);
            Array.from(productSelect.options).forEach((o) => {
                o.selected = set.has(o.value);
            });
            if (![...productSelect.selectedOptions].length && productSelect.options.length) {
                Array.from(productSelect.options).forEach((o) => {
                    o.selected = set.size === 0;
                });
            }
        }
        if (periodSelect && view.time_period) periodSelect.value = view.time_period;
        if (sourceSelect && view.data_source) sourceSelect.value = view.data_source;

        if (typeof global.applyFilters === "function") global.applyFilters();
    }

    function saveCurrentView() {
        const name = prompt("为当前筛选命名（如「CS2+Dota 本周」）：");
        if (!name || !name.trim()) return false;
        const view = captureCurrent();
        view.name = name.trim();
        view.saved_at = new Date().toISOString();
        const list = readAll().filter((v) => v.name !== view.name);
        list.unshift(view);
        writeAll(list);
        renderSelect();
        return true;
    }

    function deleteView(name) {
        if (!name || !confirm('删除视图「' + name + '」？')) return;
        writeAll(readAll().filter((v) => v.name !== name));
        renderSelect();
    }

    function renderSelect() {
        const sel = document.getElementById("filter-views-select");
        if (!sel) return;
        const list = readAll();
        const prev = sel.value;
        sel.innerHTML =
            '<option value="">已保存的视图…</option>' +
            list
                .map(
                    (v) =>
                        '<option value="' +
                        encodeURIComponent(v.name) +
                        '">' +
                        (v.name || "未命名") +
                        "</option>"
                )
                .join("");
        if (prev && list.some((v) => v.name === decodeURIComponent(prev))) {
            sel.value = prev;
        }
    }

    function mountControls() {
        const sel = document.getElementById("filter-views-select");
        if (sel) {
            sel.onchange = () => {
                const name = decodeURIComponent(sel.value || "");
                if (!name) return;
                const view = readAll().find((v) => v.name === name);
                applyView(view);
            };
        }
        const saveBtn = document.getElementById("save-filter-view-btn");
        if (saveBtn) saveBtn.onclick = () => saveCurrentView();
        const delBtn = document.getElementById("delete-filter-view-btn");
        if (delBtn) {
            delBtn.onclick = () => {
                const name = decodeURIComponent(document.getElementById("filter-views-select")?.value || "");
                if (name) deleteView(name);
            };
        }
        renderSelect();
    }

    global.DashboardFilterViews = {
        readAll,
        captureCurrent,
        applyView,
        saveCurrentView,
        mountControls,
        renderSelect,
    };
})(typeof window !== "undefined" ? window : globalThis);

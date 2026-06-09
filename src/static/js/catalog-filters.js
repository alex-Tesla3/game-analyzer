/**
 * Shared product/period filter catalog + session persistence across dashboard, metrics, comments.
 */
(function (global) {
    "use strict";

    const STORAGE_PRODUCT = "ga_filter_product";
    const STORAGE_PERIOD = "ga_filter_period";
    const STORAGE_PRODUCTS_MULTI = "ga_filter_products_multi";

    function normalizeProductId(value) {
        const pid = String(value || "").trim();
        if (pid.startsWith("steam_") && /^\d+$/.test(pid.slice(6))) {
            return pid.slice(6);
        }
        return pid;
    }

    function readStoredProduct(singleSelect) {
        try {
            const multi = sessionStorage.getItem(STORAGE_PRODUCTS_MULTI);
            if (multi && singleSelect && singleSelect.multiple) {
                return JSON.parse(multi);
            }
            const single = sessionStorage.getItem(STORAGE_PRODUCT);
            return single || "all";
        } catch {
            return singleSelect && singleSelect.multiple ? [] : "all";
        }
    }

    function writeStoredProduct(selectEl) {
        if (!selectEl) return;
        try {
            if (selectEl.multiple) {
                const ids = Array.from(selectEl.selectedOptions).map((o) => o.value);
                sessionStorage.setItem(STORAGE_PRODUCTS_MULTI, JSON.stringify(ids));
            } else {
                sessionStorage.setItem(STORAGE_PRODUCT, selectEl.value || "all");
            }
        } catch (_) {
            /* ignore */
        }
    }

    function writeStoredPeriod(value) {
        try {
            if (value) sessionStorage.setItem(STORAGE_PERIOD, value);
        } catch (_) {
            /* ignore */
        }
    }

    function readStoredPeriod() {
        try {
            return sessionStorage.getItem(STORAGE_PERIOD) || "all";
        } catch {
            return "all";
        }
    }

    async function fetchCatalog(token) {
        const fetchFn = (typeof authFetch !== "undefined" ? authFetch : fetch);
        const response = await fetchFn(`/api/options`);
        if (!response.ok) return null;
        const result = await response.json();
        return result.success ? result : null;
    }

    function populateSingleProductSelect(selectEl, products, options) {
        options = options || {};
        if (!selectEl || !Array.isArray(products) || !products.length) return;
        const includeAll = options.includeAll !== false;
        const stored = options.preserveValue !== undefined ? options.preserveValue : readStoredProduct(selectEl);
        selectEl.innerHTML = "";
        if (includeAll) {
            const allOpt = document.createElement("option");
            allOpt.value = "all";
            allOpt.textContent = "全部产品";
            selectEl.appendChild(allOpt);
        }
        products.forEach((item) => {
            const opt = document.createElement("option");
            opt.value = item.id;
            opt.textContent = item.name || item.id;
            selectEl.appendChild(opt);
        });
        if (Array.isArray(stored)) {
            return;
        }
        const has = Array.from(selectEl.options).some((o) => o.value === stored);
        selectEl.value = has ? stored : includeAll ? "all" : products[0]?.id || "all";
        if (!has && stored && stored !== "all") {
            try {
                sessionStorage.setItem(STORAGE_PRODUCT, "all");
            } catch (_) {
                /* ignore */
            }
        }
    }

    function populatePeriodSelect(selectEl, timePeriods, options) {
        options = options || {};
        if (!selectEl || !Array.isArray(timePeriods) || !timePeriods.length) return;
        const stored =
            options.preserveValue !== undefined ? options.preserveValue : readStoredPeriod();
        selectEl.innerHTML = '<option value="all">全部周期</option>';
        timePeriods.forEach((item) => {
            const opt = document.createElement("option");
            opt.value = item.id;
            opt.textContent = item.name || item.id;
            selectEl.appendChild(opt);
        });
        const has = Array.from(selectEl.options).some((o) => o.value === stored);
        selectEl.value = has ? stored : "all";
        if (!has && stored && stored !== "all") {
            try {
                sessionStorage.setItem(STORAGE_PERIOD, "all");
            } catch (_) {
                /* ignore */
            }
        }
    }

    function bindPersistence(selectEl, onChange) {
        if (!selectEl) return;
        selectEl.addEventListener("change", () => {
            writeStoredProduct(selectEl);
            if (selectEl.id === "period-select" || selectEl.id === "time-period-select") {
                writeStoredPeriod(selectEl.value);
            }
            if (typeof onChange === "function") onChange();
        });
    }

    function syncProductNamesMap(products, targetMap) {
        const map = targetMap || {};
        (products || []).forEach((p) => {
            map[p.id] = p.name || p.id;
            map[normalizeProductId(p.id)] = p.name || p.id;
        });
        return map;
    }

    global.CatalogFilters = {
        STORAGE_PRODUCT,
        STORAGE_PERIOD,
        STORAGE_PRODUCTS_MULTI,
        normalizeProductId,
        fetchCatalog,
        populateSingleProductSelect,
        populatePeriodSelect,
        bindPersistence,
        readStoredProduct,
        readStoredPeriod,
        writeStoredProduct,
        writeStoredPeriod,
        syncProductNamesMap,
    };
})(typeof window !== "undefined" ? window : globalThis);

/**
 * Mouse-friendly multi product picker (replaces native <select multiple>).
 */
(function (global) {
    "use strict";

    const DEFAULT_MOUNT = "product-picker";
    const HIDDEN_SELECT_ID = "product-select";

    function esc(s) {
        const d = document.createElement("div");
        d.textContent = s || "";
        return d.innerHTML;
    }

    function getHiddenSelect() {
        return document.getElementById(HIDDEN_SELECT_ID);
    }

    function getMountId(mountId) {
        return mountId || DEFAULT_MOUNT;
    }

    function readCheckedIds(mountId) {
        const root = document.getElementById(getMountId(mountId));
        if (!root) return [];
        return Array.from(root.querySelectorAll('input[type="checkbox"][data-product-id]:checked')).map(
            (el) => el.getAttribute("data-product-id") || ""
        );
    }

    function syncHiddenSelectFromCheckboxes(mountId) {
        const select = getHiddenSelect();
        const ids = new Set(readCheckedIds(mountId));
        if (!select) return ids;
        Array.from(select.options).forEach((opt) => {
            opt.selected = ids.has(opt.value);
        });
        return ids;
    }

    function render(mountId, products, options) {
        options = options || {};
        const root = document.getElementById(getMountId(mountId));
        const select = getHiddenSelect();
        if (!root || !Array.isArray(products)) return;

        const selectedIds =
            options.selectedIds instanceof Set
                ? options.selectedIds
                : new Set(options.selectedIds || []);
        const defaultCount = options.defaultCount ?? 2;
        const emptyHint = options.emptyHint || "暂无产品，请先在「一键采集」或 MVP 页导入数据";

        select.innerHTML = "";
        if (!products.length) {
            root.innerHTML =
                '<p class="product-picker-empty">' + esc(emptyHint) + "</p>";
            return;
        }

        let html = "";
        products.forEach((item, index) => {
            const id = String(item.id || "");
            const name = item.name || id;
            const checked = selectedIds.size
                ? selectedIds.has(id)
                : index < Math.min(defaultCount, products.length);
            html +=
                '<label class="product-picker-item">' +
                '<input type="checkbox" data-product-id="' +
                esc(id) +
                '"' +
                (checked ? " checked" : "") +
                ">" +
                '<span class="product-picker-name">' +
                esc(name) +
                "</span>" +
                (item.genre
                    ? '<span class="product-picker-genre">' + esc(item.genre) + "</span>"
                    : "") +
                "</label>";

            const opt = document.createElement("option");
            opt.value = id;
            opt.textContent = name;
            opt.selected = checked;
            select.appendChild(opt);
        });
        root.innerHTML = html;

        root.querySelectorAll('input[type="checkbox"][data-product-id]').forEach((input) => {
            input.addEventListener("change", () => {
                syncHiddenSelectFromCheckboxes(mountId);
                if (typeof options.onChange === "function") options.onChange(readCheckedIds(mountId));
            });
        });

        syncHiddenSelectFromCheckboxes(mountId);
    }

    function getSelectedIds(mountId) {
        syncHiddenSelectFromCheckboxes(mountId);
        const ids = readCheckedIds(mountId);
        if (ids.length) return ids;
        const select = getHiddenSelect();
        if (!select) return [];
        return Array.from(select.selectedOptions).map((o) => o.value);
    }

    function restoreStoredSelection(mountId, ids) {
        if (!Array.isArray(ids) || !ids.length) return;
        const idSet = new Set(ids);
        const root = document.getElementById(getMountId(mountId));
        if (!root) return;
        root.querySelectorAll('input[type="checkbox"][data-product-id]').forEach((input) => {
            input.checked = idSet.has(input.getAttribute("data-product-id") || "");
        });
        syncHiddenSelectFromCheckboxes(mountId);
    }

    global.ProductPicker = {
        HIDDEN_SELECT_ID,
        DEFAULT_MOUNT,
        render,
        getSelectedIds,
        readCheckedIds,
        syncHiddenSelectFromCheckboxes,
        restoreStoredSelection,
    };
})(typeof window !== "undefined" ? window : globalThis);

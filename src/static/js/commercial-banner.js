/**
 * Global commercial / demo environment banner from GET /api/commercial/status
 */
(function (global) {
    "use strict";

    let cachedStatus = null;

    function esc(s) {
        const d = document.createElement("div");
        d.textContent = s || "";
        return d.innerHTML;
    }

    async function fetchStatus() {
        if (cachedStatus) return cachedStatus;
        try {
            const res = await fetch("/api/commercial/status");
            if (!res.ok) return null;
            const data = await res.json();
            if (data.success) cachedStatus = data;
            return cachedStatus;
        } catch {
            return null;
        }
    }

    function shouldShowBanner(status) {
        if (!status) return false;
        if (status.deploy_profile === "public_demo" || status.deploy_profile === "development") {
            return true;
        }
        if (status.payment_mode === "demo" || status.payment_mode === "blocked") {
            return true;
        }
        if (status.production_warnings && status.production_warnings.length) {
            return true;
        }
        return false;
    }

    function bannerHtml(status) {
        const profile = status.deploy_profile_label || status.deploy_profile;
        const parts = ["<strong>" + esc(profile) + "</strong>"];
        if (status.payment_message) {
            parts.push(esc(status.payment_message));
        }
        const links =
            '<a href="' +
            esc(status.data_trust_path || "/trust") +
            '">数据说明</a>' +
            (status.pricing_path
                ? ' · <a href="' + esc(status.pricing_path) + '">订阅</a>'
                : "");
        return (
            '<div class="commercial-env-banner" role="status">' +
            '<span class="commercial-env-banner-text">' +
            parts.join(" — ") +
            "</span>" +
            '<span class="commercial-env-banner-links">' +
            links +
            "</span></div>"
        );
    }

    async function mount(containerId, options) {
        options = options || {};
        const el =
            typeof containerId === "string"
                ? document.getElementById(containerId)
                : containerId;
        if (!el) return;

        const status = await fetchStatus();
        if (!status) return;
        if (options.onlyIfDemo && !shouldShowBanner(status)) return;
        if (!shouldShowBanner(status) && !options.force) return;

        el.innerHTML = bannerHtml(status);
        el.style.display = "block";
    }

    global.CommercialBanner = {
        fetchStatus,
        mount,
        shouldShowBanner,
    };
})(typeof window !== "undefined" ? window : globalThis);

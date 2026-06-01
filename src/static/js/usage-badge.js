/** Monthly API usage badge for commercial transparency. */
(function (global) {
    async function fetchUsage(token) {
        if (!token) return null;
        try {
            const res = await fetch("/api/user?token=" + encodeURIComponent(token));
            if (!res.ok) return null;
            return await res.json();
        } catch (_) {
            return null;
        }
    }

    function render(containerId, user, opts) {
        opts = opts || {};
        const el = document.getElementById(containerId);
        if (!el || !user) return;
        const quota = user.api_quota_monthly ?? user.api_quota;
        const used = user.api_usage ?? 0;
        const remaining = user.api_remaining;
        if (quota == null || quota < 0) {
            el.textContent = (user.plan || "pro").toUpperCase() + " · 不限 API";
            return;
        }
        const pct = quota ? Math.min(100, Math.round((used / quota) * 100)) : 0;
        const warn = pct >= 85 ? "color:#f87171;" : pct >= 60 ? "color:#fcd34d;" : "color:#94a3b8;";
        el.innerHTML =
            '<span style="font-size:0.8rem;' +
            warn +
            '">API ' +
            used +
            "/" +
            quota +
            (remaining != null ? " · 剩余 " + remaining : "") +
            "</span>";
        if (opts.linkPricing && pct >= 85) {
            el.innerHTML +=
                ' · <a href="/pricing" style="color:#67e8f9;font-size:0.8rem;">升级</a>';
        }
    }

    async function mount(containerId, getToken, opts) {
        const token = typeof getToken === "function" ? getToken() : getToken;
        const user = await fetchUsage(token);
        render(containerId, user, opts);
        return user;
    }

    global.UsageBadge = { fetchUsage, render, mount };
})(typeof window !== "undefined" ? window : globalThis);

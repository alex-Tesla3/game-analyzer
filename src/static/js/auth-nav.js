/** Auth-aware navigation — skip login when session is still valid. */
(function (global) {
    async function validateToken(token) {
        if (!token) return false;
        try {
            const fetchFn = global.authFetch || fetch;
            const res = await fetchFn("/api/user");
            return res.ok;
        } catch (_) {
            return false;
        }
    }

    async function goWithAuth(targetPath, opts) {
        opts = opts || {};
        const token = global.getAuthToken && global.getAuthToken();
        if (token && (await validateToken(token))) {
            global.location.href = targetPath;
            return true;
        }
        if (opts.statusEl) opts.statusEl.textContent = opts.statusHint || "请先登录…";
        global.location.href =
            "/login?redirect=" + encodeURIComponent(targetPath);
        return false;
    }

    async function redirectIfLoggedIn() {
        const params = new URLSearchParams(global.location.search);
        const redirect = params.get("redirect");
        if (!redirect) return false;
        const token = global.getAuthToken && global.getAuthToken();
        if (!token || !(await validateToken(token))) return false;
        global.location.href = redirect;
        return true;
    }

    function apiErrorMessage(data, fallback) {
        fallback = fallback || "失败";
        if (!data || typeof data !== "object") return fallback;
        if (data.message) return String(data.message);
        const detail = data.detail;
        if (typeof detail === "string" && detail) return detail;
        if (Array.isArray(detail)) {
            const parts = detail
                .map((item) => (item && (item.msg || item.message)) || "")
                .filter(Boolean);
            if (parts.length) return parts.join("；");
        }
        return fallback;
    }

    global.AuthNav = { goWithAuth, redirectIfLoggedIn, validateToken, apiErrorMessage };
})(typeof window !== "undefined" ? window : globalThis);

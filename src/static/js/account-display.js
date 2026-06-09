/**
 * Show logged-in account on authenticated pages (fetches /api/user).
 */
(function () {
    const ROLE_LABELS = {
        admin: "管理员",
        agent: "人工坐席",
        user: "用户",
    };

    function fallbackUsername() {
        if (typeof getAuthUsername === "function") {
            return getAuthUsername() || "—";
        }
        return (
            sessionStorage.getItem("username") ||
            localStorage.getItem("username") ||
            "—"
        );
    }

    async function fetchAccount() {
        const token =
            typeof getAuthToken === "function"
                ? getAuthToken()
                : localStorage.getItem("access_token");
        if (!token) return null;
        try {
            const fetchFn = typeof authFetch === "function" ? authFetch : fetch;
            const response = await fetchFn("/api/user");
            if (!response.ok) return null;
            return await response.json();
        } catch (err) {
            console.warn("Failed to load account info:", err);
            return null;
        }
    }

    function formatBadge(user) {
        const username = user.username || "";
        const display = (user.full_name || "").trim() || username;
        const roleLabel = ROLE_LABELS[user.role] || user.role || "";
        const text = roleLabel ? `${display}（${roleLabel}）` : display;
        return { text, title: `登录账号：${username}` };
    }

    window.initAccountDisplay = async function initAccountDisplay() {
        const nodes = document.querySelectorAll("[data-account-badge]");
        if (!nodes.length) return null;

        const user = await fetchAccount();
        const fallbackName = fallbackUsername();

        nodes.forEach((el) => {
            if (user) {
                const { text, title } = formatBadge(user);
                el.textContent = text;
                el.title = title;
                el.setAttribute("data-username", user.username || "");
                el.setAttribute("data-role", user.role || "");
            } else {
                el.textContent = fallbackName;
                el.title = "登录账号：" + fallbackName;
            }
        });

        return user;
    };

    function boot() {
        const token =
            typeof getAuthToken === "function"
                ? getAuthToken()
                : localStorage.getItem("access_token");
        if (!token) return;
        initAccountDisplay();
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", boot);
    } else {
        boot();
    }
})();

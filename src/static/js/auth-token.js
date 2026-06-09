/**
 * Per-tab auth tokens (sessionStorage) with localStorage mirror for legacy pages.
 */
(function () {
    const TOKEN_KEY = "access_token";
    const USER_KEY = "username";
    const ROLE_KEY = "user_role";

    function getAuthToken() {
        const sessionToken = sessionStorage.getItem(TOKEN_KEY);
        if (sessionToken) return sessionToken;
        return localStorage.getItem(TOKEN_KEY) || localStorage.getItem("token");
    }

    function setAuthToken(token) {
        sessionStorage.setItem(TOKEN_KEY, token);
        // Mirror so legacy code (onboarding, inline fetch) still sees the session.
        localStorage.setItem(TOKEN_KEY, token);
        localStorage.removeItem("token");
    }

    function clearAuthToken() {
        sessionStorage.removeItem(TOKEN_KEY);
        localStorage.removeItem(TOKEN_KEY);
        localStorage.removeItem("token");
        sessionStorage.removeItem(USER_KEY);
        localStorage.removeItem(USER_KEY);
        sessionStorage.removeItem(ROLE_KEY);
        localStorage.removeItem(ROLE_KEY);
        sessionStorage.removeItem("user_full_name");
        localStorage.removeItem("user_full_name");
        sessionStorage.removeItem("token_type");
        localStorage.removeItem("token_type");
    }

    function getAuthUsername() {
        return sessionStorage.getItem(USER_KEY) || localStorage.getItem(USER_KEY) || "";
    }

    function setAuthUser(username, role, fullName) {
        if (username) {
            sessionStorage.setItem(USER_KEY, username);
            localStorage.setItem(USER_KEY, username);
        }
        if (role) {
            sessionStorage.setItem(ROLE_KEY, role);
            localStorage.setItem(ROLE_KEY, role);
        }
        if (fullName) {
            sessionStorage.setItem("user_full_name", fullName);
            localStorage.setItem("user_full_name", fullName);
        }
    }

    /**
     * Normalize legacy ?token= on API URLs so stale query tokens cannot override Bearer.
     */
    function normalizeApiUrl(url, token) {
        if (!token || typeof url !== "string" || !url.startsWith("/api/")) {
            return url;
        }
        try {
            var parsed = new URL(url, window.location.origin);
            if (parsed.searchParams.has("token")) {
                parsed.searchParams.set("token", token);
                return parsed.pathname + parsed.search;
            }
            parsed.searchParams.set("token", token);
            return parsed.pathname + parsed.search;
        } catch (_) {
            if (url.indexOf("token=") >= 0) {
                return url.replace(/([?&])token=[^&]*/i, "$1token=" + encodeURIComponent(token));
            }
            var sep = url.indexOf("?") >= 0 ? "&" : "?";
            return url + sep + "token=" + encodeURIComponent(token);
        }
    }

    /**
     * Drop-in fetch() that sends Authorization: Bearer and syncs ?token= fallback.
     */
    function authFetch(url, options) {
        options = options || {};
        var token = getAuthToken();
        if (token) {
            var headers = new Headers(options.headers || {});
            if (!headers.has("Authorization")) {
                headers.set("Authorization", "Bearer " + token);
            }
            options = Object.assign({}, options, { headers: headers });
            url = normalizeApiUrl(url, token);
        }
        return fetch(url, options);
    }

    function redirectToLogin(redirectPath) {
        var path = redirectPath || location.pathname + location.search;
        var url =
            "/login?redirect=" +
            encodeURIComponent(path) +
            "&reason=expired";
        clearAuthToken();
        location.replace(url);
    }

    window.getAuthToken = getAuthToken;
    window.setAuthToken = setAuthToken;
    window.clearAuthToken = clearAuthToken;
    window.getAuthUsername = getAuthUsername;
    window.setAuthUser = setAuthUser;
    window.authFetch = authFetch;
    window.redirectToLogin = redirectToLogin;
    if (typeof window.getToken === "undefined") {
        window.getToken = getAuthToken;
    }
})();

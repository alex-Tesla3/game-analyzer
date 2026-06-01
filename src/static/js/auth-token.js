/**
 * Per-tab auth tokens (sessionStorage) so multiple accounts can be open in different tabs.
 * Falls back to legacy localStorage for older sessions.
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
        localStorage.removeItem(TOKEN_KEY);
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
            localStorage.removeItem(USER_KEY);
        }
        if (role) {
            sessionStorage.setItem(ROLE_KEY, role);
            localStorage.removeItem(ROLE_KEY);
        }
        if (fullName) {
            sessionStorage.setItem("user_full_name", fullName);
            localStorage.removeItem("user_full_name");
        }
    }

    window.getAuthToken = getAuthToken;
    window.setAuthToken = setAuthToken;
    window.clearAuthToken = clearAuthToken;
    window.getAuthUsername = getAuthUsername;
    window.setAuthUser = setAuthUser;
    if (typeof window.getToken === "undefined") {
        window.getToken = getAuthToken;
    }
})();

/**
 * Admin-only: account badge + single「系统管理」entry (users + LLM tabs on /admin).
 */
(function (global) {
    "use strict";

    async function fetchProfile() {
        const token = global.getAuthToken && global.getAuthToken();
        if (!token) return null;
        try {
            const fetchFn = global.authFetch || fetch;
            const res = await fetchFn("/api/user");
            if (!res.ok) return null;
            return await res.json();
        } catch (err) {
            console.warn("AdminMenu: failed to load profile", err);
            return null;
        }
    }

    function isAdmin(profile) {
        return profile && profile.role === "admin";
    }

    function injectUserMenuDropdowns() {
        global.document.querySelectorAll(".user-menu-dropdown, #user-menu-dropdown").forEach(function (menu) {
            if (menu.querySelector("[data-admin-menu]")) return;

            var divider = document.createElement("div");
            divider.className = "dropdown-divider";
            divider.setAttribute("data-admin-menu", "1");

            var adminBtn = document.createElement("button");
            adminBtn.type = "button";
            adminBtn.className = "dropdown-item";
            adminBtn.setAttribute("data-admin-menu", "1");
            adminBtn.textContent = "⚙️ 系统管理";
            adminBtn.addEventListener("click", function (e) {
                e.preventDefault();
                global.location.href = "/admin";
            });

            var block = document.createDocumentFragment();
            block.appendChild(divider);
            block.appendChild(adminBtn);

            var pricingBtn = null;
            menu.querySelectorAll(".dropdown-item").forEach(function (btn) {
                if ((btn.textContent || "").indexOf("订阅") >= 0) pricingBtn = btn;
            });
            if (pricingBtn) {
                menu.insertBefore(block, pricingBtn);
            } else {
                menu.appendChild(block);
            }
        });
    }

    function injectAppNavMore() {
        var menu = global.document.getElementById("app-nav-dropdown");
        if (!menu || menu.querySelector("[data-admin-nav]")) return;

        var divider = document.createElement("div");
        divider.className = "app-nav-divider";

        var adminLink = document.createElement("a");
        adminLink.href = "/admin";
        adminLink.setAttribute("data-admin-nav", "1");
        adminLink.textContent = "系统管理";

        menu.appendChild(divider);
        menu.appendChild(adminLink);
    }

    async function apply() {
        if (typeof global.initAccountDisplay === "function") {
            await global.initAccountDisplay();
        }
        var profile = await fetchProfile();
        if (!isAdmin(profile)) return;
        injectUserMenuDropdowns();
        injectAppNavMore();
        return profile;
    }

    function boot() {
        apply();
    }

    if (global.document.readyState === "loading") {
        global.document.addEventListener("DOMContentLoaded", function () {
            setTimeout(boot, 80);
        });
    } else {
        setTimeout(boot, 80);
    }

    global.AdminMenu = { apply: apply, fetchProfile: fetchProfile, isAdmin: isAdmin };
})(typeof window !== "undefined" ? window : globalThis);

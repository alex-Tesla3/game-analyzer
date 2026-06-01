/**
 * Stable browser device id for anti-abuse (registration limits, shared free API pool).
 * Stored in localStorage so it persists across sessions on the same browser.
 */
(function () {
    const STORAGE_KEY = "ga_device_id";

    function hashString(input) {
        let h = 2166136261;
        for (let i = 0; i < input.length; i++) {
            h ^= input.charCodeAt(i);
            h = Math.imul(h, 16777619);
        }
        return (h >>> 0).toString(36);
    }

    function buildSeed() {
        const parts = [
            navigator.userAgent || "",
            navigator.language || "",
            String(screen.width || 0),
            String(screen.height || 0),
            String(screen.colorDepth || 0),
            String(new Date().getTimezoneOffset()),
            navigator.platform || "",
        ];
        return parts.join("|");
    }

    function generateDeviceId() {
        const seed = buildSeed();
        const rand = Math.random().toString(36).slice(2, 10);
        return "dev_" + hashString(seed + rand) + rand;
    }

    function getDeviceId() {
        try {
            let id = localStorage.getItem(STORAGE_KEY);
            if (!id || id.length < 8) {
                id = generateDeviceId();
                localStorage.setItem(STORAGE_KEY, id);
            }
            return id;
        } catch (e) {
            return generateDeviceId();
        }
    }

    function patchFetch() {
        if (window.__gaDeviceFetchPatched) return;
        window.__gaDeviceFetchPatched = true;
        const original = window.fetch.bind(window);
        window.fetch = function (input, init) {
            init = init || {};
            const headers = new Headers(init.headers || {});
            const deviceId = getDeviceId();
            if (deviceId && !headers.has("X-Device-Id")) {
                headers.set("X-Device-Id", deviceId);
            }
            init.headers = headers;
            return original(input, init);
        };
    }

    window.getDeviceId = getDeviceId;
    patchFetch();
})();

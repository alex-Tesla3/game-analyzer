/** First-run onboarding wizard on dashboard. */
(function (global) {
    const STORAGE_KEY = "ga_onboarding_done_v1";

    const STEPS = [
        {
            title: "① 打开分析向导",
            body: "输入游戏名（如 CS2）或 AppID，一键完成抓取、报告与归档。",
            action: { label: "开始分析", href: "/guide" },
        },
        {
            title: "② 导出行动清单",
            body: "P0/P1 任务可导出 CSV / 飞书 / Jira，排进迭代 backlog。",
            action: { label: "落地指导", href: "/work#actions" },
        },
        {
            title: "③ 复测验证",
            body: "2 周后从归档一键复测，系统自动对比口碑并更新验证状态。",
            action: { label: "复盘归档", href: "/games/review#archives" },
        },
    ];

    function esc(s) {
        const d = document.createElement("div");
        d.textContent = s || "";
        return d.innerHTML;
    }

    function isDone() {
        try {
            return localStorage.getItem(STORAGE_KEY) === "1";
        } catch {
            return false;
        }
    }

    function markDone() {
        try {
            localStorage.setItem(STORAGE_KEY, "1");
        } catch (_) { /* ignore */ }
    }

    function render(containerId) {
        const el = document.getElementById(containerId);
        if (!el || isDone()) return;

        el.innerHTML =
            '<div class="onboarding-wizard">' +
            '<div class="onboarding-head"><h3>🚀 首次使用 · 三步开始真实竞品分析</h3>' +
            '<button type="button" class="onboarding-dismiss" id="onboarding-dismiss">不再显示</button></div>' +
            '<div class="onboarding-steps">' +
            STEPS.map(
                (s) =>
                    '<div class="onboarding-step"><h4>' +
                    esc(s.title) +
                    "</h4><p>" +
                    esc(s.body) +
                    '</p><a class="onboarding-link" href="' +
                    esc(s.action.href) +
                    '">' +
                    esc(s.action.label) +
                    " →</a></div>"
            ).join("") +
            "</div></div>";

        document.getElementById("onboarding-dismiss").onclick = () => {
            markDone();
            el.innerHTML = "";
        };
    }

    async function maybeShowAfterLibraryCheck(containerId, token) {
        if (isDone() || !token) return;
        try {
            const res = await fetch(
                "/api/games/library?token=" + encodeURIComponent(token)
            );
            if (!res.ok) return;
            const data = await res.json();
            const steamCount = (data.games || []).filter((g) =>
                String(g.source || "").includes("mvp")
            ).length;
            if (steamCount >= 3) {
                markDone();
                return;
            }
            render(containerId);
        } catch (_) {
            render(containerId);
        }
    }

    global.OnboardingWizard = {
        render,
        maybeShowAfterLibraryCheck,
        markDone,
    };
})(typeof window !== "undefined" ? window : globalThis);

/** Renders the commercial work-guidance loop (analyze → export → share → retest). */
(function (global) {
    function esc(s) {
        const d = document.createElement("div");
        d.textContent = s || "";
        return d.innerHTML;
    }

    function renderSteps(container, steps) {
        if (!container || !steps?.length) return;
        container.innerHTML =
            '<ol class="wg-steps">' +
            steps
                .map((s) => {
                    const mark = s.done ? "✅" : "○";
                    return (
                        '<li class="' +
                        (s.done ? "done" : "") +
                        '"><span class="wg-mark">' +
                        mark +
                        "</span><div><strong>" +
                        esc(s.label) +
                        "</strong><p>" +
                        esc(s.detail) +
                        '</p><a href="' +
                        esc(s.href) +
                        '">' +
                        (s.done ? "查看" : "去做") +
                        " →</a></div></li>"
                    );
                })
                .join("") +
            "</ol>";
    }

    function renderActions(container, items, archiveId, token) {
        if (!container) return;
        if (!items?.length) {
            container.innerHTML = '<p class="wg-hint">暂无行动清单。请先在<a href="/guide">分析向导</a>生成报告。</p>';
            return;
        }
        if (global.ScenarioReport) {
            container.innerHTML =
                '<div class="wg-actions-bar">' +
                '<button type="button" class="wg-btn" data-fmt="csv">⬇️ CSV</button>' +
                '<button type="button" class="wg-btn" data-fmt="feishu">📋 飞书</button>' +
                '<button type="button" class="wg-btn" data-fmt="jira">📋 Jira</button>' +
                (archiveId
                    ? '<button type="button" class="wg-btn wg-primary" id="wg-retest">🔄 复测</button>'
                    : "") +
                "</div>" +
                ScenarioReport.renderActionItems(items, {
                    interactive: !!archiveId,
                    archiveId: archiveId || "",
                });
            container.querySelectorAll("[data-fmt]").forEach((btn) => {
                btn.onclick = () =>
                    ScenarioReport.exportActions(items, token, btn.getAttribute("data-fmt"));
            });
            const retest = container.querySelector("#wg-retest");
            if (retest && archiveId) {
                retest.onclick = async () => {
                    retest.disabled = true;
                    retest.textContent = "复测中…";
                    const res = await fetch(
                        "/api/games/archives/" +
                            encodeURIComponent(archiveId) +
                            "/retest?token=" +
                            encodeURIComponent(token),
                        { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" }
                    );
                    const data = await res.json();
                    retest.textContent = data.success ? "✅ 复测完成" : "失败";
                    if (data.success && global.location) location.reload();
                };
            }
            if (archiveId) {
                ScenarioReport.bindActionStatusSelects(container, token);
            }
        }
    }

    async function loadPage(token) {
        const fetchFn = typeof authFetch !== "undefined" ? authFetch : fetch;
        const res = await fetchFn("/api/work/guidance");
        return res.json();
    }

    global.WorkGuidance = { renderSteps, renderActions, loadPage, esc };
})(typeof window !== "undefined" ? window : globalThis);

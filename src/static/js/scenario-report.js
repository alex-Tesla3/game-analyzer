/** Shared AI scenario report UI for compare / library / review pages. */
(function (global) {
    function esc(s) {
        const d = document.createElement("div");
        d.textContent = s || "";
        return d.innerHTML;
    }

    function formatStatus(data) {
        if (!data || !data.success) {
            return data?.message || "生成失败";
        }
        if (data.using_llm) {
            return data.llm_error ? "AI 已生成（部分回退规则引擎）" : "AI 报告已生成";
        }
        if (data.llm_error) {
            return "规则报告已生成（LLM 解析失败）";
        }
        return "规则报告已生成";
    }

    function renderDimensionScores(data) {
        const rows = data.dimension_scores || (data.facts && data.facts.dimension_scores) || [];
        const dims = (data.facts && data.facts.score_dimensions) || [];
        if (!rows.length || !dims.length) return "";
        const head = dims.map((d) => "<th>" + esc(d.title) + "</th>").join("");
        const body = rows
            .map((row) => {
                const cells = dims
                    .map((d) => {
                        const v = (row.scores || {})[d.key];
                        return "<td>" + esc(v != null ? String(v) : "—") + "</td>";
                    })
                    .join("");
                const custom = row.is_custom ? " ✎" : "";
                return "<tr><th>" + esc(row.name) + custom + "</th>" + cells + "</tr>";
            })
            .join("");
        return (
            '<div class="sr-dim-scores"><h4>六维评分</h4>' +
            '<table class="sr-score-table"><thead><tr><th>游戏</th>' +
            head +
            "</tr></thead><tbody>" +
            body +
            "</tbody></table></div>"
        );
    }

    function renderActionItems(items, opts) {
        if (!items || !items.length) return "";
        opts = opts || {};
        const interactive = !!opts.interactive;
        const archiveId = opts.archiveId || "";
        const rows = items
            .map(
                (a, idx) => {
                    const id = a.id != null ? String(a.id) : String(idx);
                    const status = a.status || "pending";
                    const statusCell = interactive
                        ? '<select class="action-status" data-id="' + esc(id) + '" data-archive="' + esc(archiveId) + '">' +
                          ["pending","in_progress","done","verified","not_met"].map(s =>
                            '<option value="' + s + '"' + (s === status ? " selected" : "") + ">" +
                            esc({pending:"待办",in_progress:"进行中",done:"已完成",verified:"已验证",not_met:"未达标"}[s] || s) +
                            "</option>"
                          ).join("") + "</select>"
                        : esc({pending:"待办",in_progress:"进行中",done:"已完成",verified:"已验证",not_met:"未达标"}[status] || status);
                    const note = a.verification_note
                        ? '<div class="sr-action-note">' + esc(a.verification_note) + "</div>"
                        : "";
                    const overdue = a.overdue
                        ? '<span class="sr-overdue" style="color:#f87171;font-size:0.75rem;margin-left:4px;">逾期</span>'
                        : "";
                    const due = a.due_at
                        ? '<div class="sr-due" style="font-size:0.75rem;color:#94a3b8;">截止 ' + esc(String(a.due_at).slice(0, 10)) + "</div>"
                        : "";
                    return "<tr><td>" + esc(a.priority) + "</td><td>" + esc(a.title) + overdue + note + due +
                        "</td><td>" + esc(a.owner_role) + "</td><td>" + esc(a.action) +
                        "</td><td>" + esc(a.verify_metric) + "</td><td>" + esc(a.timeframe || "") +
                        "</td><td>" + statusCell + "</td></tr>";
                }
            )
            .join("");
        return (
            '<div class="sr-actions"><h4>可执行行动清单</h4>' +
            (opts.exportBar || "") +
            '<table class="sr-action-table"><thead><tr>' +
            "<th>优先级</th><th>事项</th><th>负责人</th><th>动作</th><th>验证</th><th>周期</th><th>状态</th>" +
            "</tr></thead><tbody>" +
            rows +
            "</tbody></table></div>"
        );
    }

    function bindActionStatusSelects(container, token, onSaved) {
        if (!container) return;
        container.querySelectorAll(".action-status").forEach((sel) => {
            sel.onchange = async () => {
                const archiveId = sel.dataset.archive;
                if (!archiveId) return;
                const res = await fetch(
                    "/api/games/archives/" + encodeURIComponent(archiveId) + "/actions?token=" + encodeURIComponent(token),
                    {
                        method: "PATCH",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ updates: { [sel.dataset.id]: { status: sel.value } } }),
                    }
                );
                const data = await res.json();
                if (data.success && onSaved) onSaved(data.action_items);
            };
        });
    }

    async function exportActions(actionItems, token, format) {
        const fmt = format || "csv";
        const res = await fetch(
            "/api/wizard/export/actions?token=" + encodeURIComponent(token) + "&format=" + encodeURIComponent(fmt),
            {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ action_items: actionItems }),
            }
        );
        if (!res.ok) return false;
        if (fmt === "feishu") {
            const text = await res.text();
            if (navigator.clipboard && navigator.clipboard.writeText) {
                await navigator.clipboard.writeText(text);
                return "clipboard";
            }
        }
        const blob = await res.blob();
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        const ext =
            fmt === "json" ? "json" : fmt === "jira" ? "jira.csv" : fmt === "feishu" ? "feishu.md" : "csv";
        a.download = "action-items." + ext;
        a.click();
        return true;
    }

    function renderResult(container, data) {
        if (!container) return;
        if (!data || !data.success) {
            container.innerHTML =
                '<p class="sr-empty">' + esc(data?.message || "生成失败") + "</p>";
            container.dataset.markdown = "";
            return;
        }
        const badge = data.using_llm
            ? '<span class="sr-badge llm">AI 生成 · ' + esc(data.llm_provider || "LLM") + "</span>"
            : '<span class="sr-badge rule">规则引擎总结</span>';
        let badges = badge;
        if (data.llm_error) {
            badges += '<span class="sr-badge warn">LLM 回退：' + esc(data.llm_error) + "</span>";
        }
        if (global.DataProvenance && data.data_source) {
            badges += global.DataProvenance.renderDataSourceBadge(data.data_source);
        }
        const sections = (data.sections || [])
            .map(
                (s) =>
                    "<section class=\"sr-section\"><h4>" +
                    esc(s.title) +
                    "</h4><p>" +
                    esc(s.content).replace(/\n/g, "<br>") +
                    "</p></section>"
            )
            .join("");
        container.innerHTML =
            '<div class="sr-result">' +
            '<div class="sr-result-head">' +
            badges +
            '<span class="sr-time">' +
            esc((data.generated_at || "").slice(0, 19)) +
            "</span></div>" +
            "<h3>" +
            esc(data.title) +
            "</h3>" +
            '<p class="sr-exec">' +
            esc(data.executive_summary) +
            "</p>" +
            renderDimensionScores(data) +
            sections +
            renderActionItems(data.action_items) +
            "</div>";
        container.dataset.markdown = data.markdown || "";
    }

    async function generate(scenario, body, token) {
        const url = "/api/scenarios/" + scenario + "/report?token=" + encodeURIComponent(token);
        try {
            const res = await fetch(url, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(body || {}),
            });
            if (res.status === 401) {
                location.href = "/login";
                return null;
            }
            let data;
            try {
                data = await res.json();
            } catch (_) {
                return { success: false, message: "服务器响应格式错误" };
            }
            if (!res.ok) {
                return {
                    success: false,
                    message: data?.detail || data?.message || "生成失败（HTTP " + res.status + "）",
                };
            }
            return data;
        } catch (err) {
            return { success: false, message: "网络错误：" + (err?.message || "请重试") };
        }
    }

    async function archiveReport(report, token) {
        const fetchFn = typeof authFetch !== "undefined" ? authFetch : fetch;
        const res = await fetchFn("/api/scenarios/archive", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ report }),
        });
        return res.json();
    }

    async function shareArchive(archiveId, token, expiresHours) {
        const fetchFn = typeof authFetch !== "undefined" ? authFetch : fetch;
        const res = await fetchFn(
            "/api/games/archives/" + encodeURIComponent(archiveId) + "/share",
            {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ expires_hours: expiresHours || 168 }),
            }
        );
        return res.json();
    }

    function copyMarkdown(container) {
        const md = container?.dataset?.markdown || container?.closest("[data-markdown]")?.dataset?.markdown;
        const text = md || container?.innerText || "";
        if (navigator.clipboard) {
            navigator.clipboard.writeText(text);
            return true;
        }
        return false;
    }

    function mountToolbar(opts) {
        const el = document.getElementById(opts.toolbarId);
        if (!el) return;
        el.innerHTML =
            '<button type="button" class="sr-btn primary" id="' +
            opts.generateBtnId +
            '">' +
            (opts.generateLabel || "🤖 生成 AI 总结报告") +
            "</button>" +
            '<button type="button" class="sr-btn" id="' +
            opts.copyBtnId +
            '">📋 复制报告</button>' +
            '<button type="button" class="sr-btn" id="' +
            opts.archiveBtnId +
            '">📁 归档</button>' +
            '<span class="sr-status" id="' +
            opts.statusId +
            '"></span>';
    }

    global.ScenarioReport = {
        esc,
        formatStatus,
        renderResult,
        renderActionItems,
        bindActionStatusSelects,
        exportActions,
        generate,
        archiveReport,
        shareArchive,
        copyMarkdown,
        mountToolbar,
    };
})(typeof window !== "undefined" ? window : globalThis);

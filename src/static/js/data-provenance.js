/** Data provenance badges for dashboard and compare views. */
(function (global) {
    const TRUST_STYLES = {
        high: { bg: 'rgba(34,197,94,0.15)', border: '#22c55e', color: '#86efac' },
        medium: { bg: 'rgba(234,179,8,0.12)', border: '#eab308', color: '#fde047' },
        low: { bg: 'rgba(239,68,68,0.12)', border: '#ef4444', color: '#fca5a5' },
    };

    function renderBadge(trust, source) {
        const level = (trust && trust.level) || 'medium';
        const style = TRUST_STYLES[level] || TRUST_STYLES.medium;
        const label = (trust && trust.label) || source || '未知来源';
        const hint = (trust && trust.hint) || '';
        return (
            '<span class="data-trust-badge" data-level="' + level + '" title="' +
            escapeAttr(hint) +
            '" style="background:' +
            style.bg +
            ';border:1px solid ' +
            style.border +
            ';color:' +
            style.color +
            '">' +
            escapeHtml(label) +
            '</span>'
        );
    }

    function escapeHtml(s) {
        return String(s || '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');
    }

    function escapeAttr(s) {
        return escapeHtml(s).replace(/"/g, '&quot;');
    }

    function renderBanner(containerId, payload) {
        const el = document.getElementById(containerId);
        if (!el || !payload) return;
        const trust = payload.trust || {};
        const badge = renderBadge(trust, payload.source);
        let extra = '';
        if (payload.show_mock_warning) {
            extra =
                '<span style="margin-left:8px;font-size:0.8rem;color:#fca5a5;">演示 KPI 已弱化显示，请优先参考 Steam 口碑指标</span>';
        }
        el.innerHTML =
            '<div style="display:flex;align-items:center;flex-wrap:wrap;gap:8px;padding:10px 14px;border-radius:10px;background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);">' +
            '<span style="font-size:0.8rem;color:#94a3b8;">当前数据：</span>' +
            badge +
            extra +
            '</div>';
        el.style.display = 'block';
        global.dataProvenance = payload;
    }

    async function fetchProvenance(token) {
        const t = token || (global.getAuthToken && global.getAuthToken()) || localStorage.getItem('access_token');
        if (!t) return null;
        const res = await fetch('/api/data/provenance?token=' + encodeURIComponent(t));
        if (!res.ok) return null;
        return res.json();
    }

    const SOURCE_LABELS = {
        imported: { label: 'Owner 导入数据', level: 'high' },
        mvp_steam: { label: 'Steam 真数据', level: 'high' },
        mvp_multi: { label: '多平台真数据', level: 'high' },
        taptap_public: { label: 'TapTap 真数据', level: 'high' },
        google_play_public: { label: 'Google Play 真数据', level: 'high' },
        cached: { label: '缓存数据', level: 'medium' },
        mock: { label: '演示 Mock', level: 'low' },
    };

    function renderDataSourceBadge(source) {
        const meta = SOURCE_LABELS[source] || { label: source || '未知', level: 'medium' };
        return renderBadge({ level: meta.level, label: meta.label, hint: '数据来源：' + meta.label }, source);
    }

    global.DataProvenance = {
        renderBadge,
        renderBanner,
        renderDataSourceBadge,
        fetchProvenance,
        SOURCE_LABELS,
    };
})(typeof window !== 'undefined' ? window : globalThis);

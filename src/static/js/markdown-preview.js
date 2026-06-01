/** Minimal Markdown → HTML for archive preview (no external deps). */
(function (global) {
    function esc(s) {
        return String(s || "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;");
    }

    function render(md) {
        if (!md) return "<p class=\"md-empty\">（空）</p>";
        const lines = String(md).split("\n");
        const out = [];
        let inUl = false;

        function closeUl() {
            if (inUl) {
                out.push("</ul>");
                inUl = false;
            }
        }

        for (let raw of lines) {
            const line = raw.trimEnd();
            if (!line.trim()) {
                closeUl();
                continue;
            }
            if (line.startsWith("### ")) {
                closeUl();
                out.push("<h4>" + inline(line.slice(4)) + "</h4>");
            } else if (line.startsWith("## ")) {
                closeUl();
                out.push("<h3>" + inline(line.slice(3)) + "</h3>");
            } else if (line.startsWith("# ")) {
                closeUl();
                out.push("<h2>" + inline(line.slice(2)) + "</h2>");
            } else if (/^[-*]\s+/.test(line)) {
                if (!inUl) {
                    out.push("<ul>");
                    inUl = true;
                }
                out.push("<li>" + inline(line.replace(/^[-*]\s+/, "")) + "</li>");
            } else if (/^\d+\.\s+/.test(line)) {
                closeUl();
                out.push("<p>" + inline(line) + "</p>");
            } else {
                closeUl();
                out.push("<p>" + inline(line) + "</p>");
            }
        }
        closeUl();
        return '<div class="md-preview">' + out.join("") + "</div>";
    }

    function inline(text) {
        let s = esc(text);
        s = s.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
        s = s.replace(/`([^`]+)`/g, "<code>$1</code>");
        return s;
    }

    global.MarkdownPreview = { render, inline };
})(typeof window !== "undefined" ? window : globalThis);

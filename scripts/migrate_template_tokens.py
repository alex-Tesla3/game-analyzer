#!/usr/bin/env python3
"""
Migrate fetch(...?token=...) → authFetch(...) in HTML template files.

Rules:
  1. Replace `fetch(` with `authFetch(` for calls that contain token= in the URL.
  2. Remove ?token=${...} when token is the FIRST query param
       /api/foo?token=${token}  → /api/foo
       /api/foo?token=${encodeURIComponent(token)}  → /api/foo
  3. Remove &token=${...} when token appears after other params
       /api/foo?a=1&token=${token}  → /api/foo?a=1
  4. Handles both  token=${token}  and  token=${encodeURIComponent(token)}
  5. Does NOT touch fetch() calls that don't have token= in the URL.
  6. Does NOT touch login.html, landing.html (no auth needed).
"""

import re
import sys
from pathlib import Path

SKIP_FILES = {"login.html", "landing.html", "pricing.html"}

_TOKEN_VAR = r'\$\{(?:encodeURIComponent\(token\)|token)\}'

# ?token=${...}  followed by & (more params) → remove and promote & → ?
PATTERN_TOKEN_FIRST_WITH_MORE = re.compile(
    r'\?token=' + _TOKEN_VAR + r'(?=&)',
)
# ?token=${...}  at end of URL (followed by `, " or whitespace/paren)
PATTERN_TOKEN_FIRST_ALONE = re.compile(
    r'\?token=' + _TOKEN_VAR + r'(?=`|"|\s*[\),])',
)
# &token=${...} anywhere in the URL
PATTERN_TOKEN_AMPERSAND = re.compile(
    r'&token=' + _TOKEN_VAR,
)


def patch_line(line: str) -> tuple[str, int]:
    """Return (patched_line, changes_count)."""
    # Only process lines that have fetch( AND token= in the URL
    if "fetch(" not in line or "token=" not in line:
        return line, 0

    original = line

    # 1a. ?token=...& → remove ?token=... and keep remaining as ?
    line = PATTERN_TOKEN_FIRST_WITH_MORE.sub("?", line)
    # 1b. ?token=... at end → remove entirely
    line = PATTERN_TOKEN_FIRST_ALONE.sub("", line)
    # 2. &token=... → remove
    line = PATTERN_TOKEN_AMPERSAND.sub("", line)

    # 3. Replace fetch( → authFetch( for lines that had token removal
    if line != original:
        line = line.replace("await fetch(", "await authFetch(")
        # Also handle non-await usages
        line = re.sub(r'(?<!\w)fetch\(', "authFetch(", line)

    return line, 1 if line != original else 0


def migrate_file(path: Path) -> int:
    if path.name in SKIP_FILES:
        print(f"  SKIP  {path.name}")
        return 0

    text = path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    new_lines = []
    total = 0
    for i, line in enumerate(lines, 1):
        new_line, changed = patch_line(line)
        if changed:
            total += changed
            print(f"    L{i:5d}: {line.rstrip()}")
            print(f"         → {new_line.rstrip()}")
        new_lines.append(new_line)

    if total:
        path.write_text("".join(new_lines), encoding="utf-8")
        print(f"  ✅ {path.name}: {total} change(s)\n")
    else:
        print(f"  ── {path.name}: nothing to change\n")

    return total


def main():
    templates_dir = Path(__file__).parent.parent / "src" / "templates"
    html_files = sorted(templates_dir.glob("*.html"))

    grand_total = 0
    for f in html_files:
        grand_total += migrate_file(f)

    print(f"\n{'='*50}")
    print(f"Total changes applied: {grand_total}")


if __name__ == "__main__":
    main()

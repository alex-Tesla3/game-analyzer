#!/usr/bin/env bash
# Run Playwright browser E2E tests.
# Uses bundled Chromium after `playwright install chromium`, or set PLAYWRIGHT_CHANNEL=chrome
# to reuse an installed Google Chrome (faster on macOS when CDN download is slow).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ -d .venv ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
elif [[ -d venv ]]; then
  # shellcheck disable=SC1091
  source venv/bin/activate
fi

python -m pip install -q "pytest>=8.4,<10" pytest-playwright "playwright>=1.49,<2" 2>/dev/null || true

if [[ -z "${PLAYWRIGHT_CHANNEL:-}" ]] && ! compgen -G "$HOME/Library/Caches/ms-playwright/chromium-*" >/dev/null 2>&1; then
  echo "Installing Playwright Chromium (or export PLAYWRIGHT_CHANNEL=chrome to skip)..."
  python -m playwright install chromium
fi

export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:$PYTHONPATH}"
python -m pytest tests/e2e -m browser -v "$@"

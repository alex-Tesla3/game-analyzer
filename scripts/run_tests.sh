#!/usr/bin/env bash
# CI-parity test runner for game_analyzer
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

export PYTHONPATH="src:."
export GA_E2E_DISABLE_RATE_LIMIT=1
export APP_ENV=development
export ALLOW_DEMO_ACCOUNTS=true
export TZ=UTC
export LANG=C.UTF-8

pytest tests/ --ignore=tests/e2e "${@:-}"

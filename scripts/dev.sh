#!/usr/bin/env bash
# Start the local portfolio/demo server with the project virtualenv.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PORT="${PORT:-8080}"
HOST="${HOST:-127.0.0.1}"

if [[ -x .venv/bin/python ]]; then
  PYTHON_BIN=".venv/bin/python"
elif [[ -x venv/bin/python ]]; then
  PYTHON_BIN="venv/bin/python"
else
  echo "No project virtualenv found. Create one with:"
  echo "  python -m venv .venv && .venv/bin/python -m pip install -r requirements.txt"
  exit 1
fi

export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:$PYTHONPATH}"
export APP_ENV="${APP_ENV:-development}"
export ALLOW_DEMO_ACCOUNTS="${ALLOW_DEMO_ACCOUNTS:-true}"

echo "Starting Game Analyzer at http://${HOST}:${PORT}"
echo "Showcase: http://${HOST}:${PORT}/showcase"
exec "$PYTHON_BIN" -m uvicorn src.web_app:app --host "$HOST" --port "$PORT" --reload

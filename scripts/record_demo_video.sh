#!/usr/bin/env bash
# Record ~60s portfolio demo video (requires server on :8080).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PORT="${PORT:-8080}"
URL="http://127.0.0.1:${PORT}"

if [[ -d .venv ]]; then source .venv/bin/activate; elif [[ -d venv ]]; then source venv/bin/activate; fi
export PYTHONPATH="src:."

if ! curl -sf "${URL}/api/health" >/dev/null 2>&1; then
  echo "Starting server on ${PORT} …"
  nohup uvicorn src.web_app:app --host 127.0.0.1 --port "${PORT}" >/tmp/game-analyzer-uvicorn.log 2>&1 &
  for _ in $(seq 1 30); do
    curl -sf "${URL}/api/health" >/dev/null 2>&1 && break
    sleep 1
  done
fi

if ! curl -sf "${URL}/api/health" >/dev/null 2>&1; then
  echo "Server not ready. See /tmp/game-analyzer-uvicorn.log"
  exit 1
fi

./scripts/seed_demo.sh >/dev/null 2>&1 || true
python scripts/record_demo_video.py

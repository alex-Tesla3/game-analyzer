#!/usr/bin/env bash
# Capture portfolio screenshots (server must be on :8080).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [[ -d .venv ]]; then source .venv/bin/activate; elif [[ -d venv ]]; then source venv/bin/activate; fi
export PYTHONPATH="src:."
python scripts/capture_screenshots.py

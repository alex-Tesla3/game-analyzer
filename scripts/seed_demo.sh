#!/usr/bin/env bash
# Bootstrap offline demo MVP data + sample archive (no network).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
source .venv/bin/activate 2>/dev/null || source venv/bin/activate
export PYTHONPATH="${ROOT}/src"
export GA_E2E_DISABLE_LLM=1
python - <<'PY'
import asyncio
from src.services.demo_pack import bootstrap_demo_pack

result = asyncio.run(bootstrap_demo_pack("demo"))
print("Demo bootstrap:", result)
PY

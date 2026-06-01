#!/usr/bin/env bash
# Expose local :8080 publicly (no Fly/Railway billing). Uses Cloudflare quick tunnel.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PORT="${PORT:-8080}"
URL="http://127.0.0.1:${PORT}"

if ! curl -sf "${URL}/api/health" >/dev/null 2>&1; then
  echo "Starting server on ${PORT} …"
  if [[ -d .venv ]]; then source .venv/bin/activate; elif [[ -d venv ]]; then source venv/bin/activate; fi
  export PYTHONPATH="src:."
  nohup uvicorn src.web_app:app --host 127.0.0.1 --port "${PORT}" >/tmp/game-analyzer-uvicorn.log 2>&1 &
  for _ in $(seq 1 30); do
    curl -sf "${URL}/api/health" >/dev/null 2>&1 && break
    sleep 1
  done
  if ! curl -sf "${URL}/api/health" >/dev/null 2>&1; then
    echo "Server failed to start. See /tmp/game-analyzer-uvicorn.log"
    exit 1
  fi
fi

if ! command -v cloudflared >/dev/null 2>&1; then
  echo "cloudflared not found."
  echo "Install: brew install cloudflared"
  echo "Or download: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/"
  exit 1
fi

echo ""
echo "Local app: ${URL}"
echo "Public tunnel starting (Ctrl+C to stop) …"
echo ""
echo "Look for a line like:"
echo "  https://xxxx.trycloudflare.com"
echo ""
echo "Share:"
echo "  /showcase   — portfolio"
echo "  /dashboard  — BI (demo / demo123)"
echo ""

# Prefer HTTP/2 when QUIC is blocked or unstable (common on some networks).
PROTO="${CLOUDFLARED_PROTOCOL:-http2}"
TUNNEL_LOG="${TUNNEL_LOG:-/tmp/game-analyzer-tunnel.log}"
TUNNEL_URL_FILE="${TUNNEL_URL_FILE:-/tmp/game-analyzer-tunnel.url}"

echo "Tunnel log: ${TUNNEL_LOG}"
echo "Public URL file: ${TUNNEL_URL_FILE}"
echo ""

cloudflared tunnel --protocol "${PROTO}" --url "${URL}" 2>&1 | tee "${TUNNEL_LOG}" | while IFS= read -r line; do
  printf '%s\n' "$line"
  url="$(printf '%s' "$line" | grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' | head -1)"
  if [[ -n "$url" ]]; then
    printf '%s\n' "$url" > "${TUNNEL_URL_FILE}"
    echo ""
    echo ">>> Public URL: ${url}"
    echo ">>> Showcase:   ${url}/showcase"
    echo ">>> Dashboard:  ${url}/dashboard  (demo / demo123)"
    echo ""
    echo ">>> 写入简历 / README 时可设: export PUBLIC_DEMO_BASE_URL=${url}"
    echo ""
  fi
done

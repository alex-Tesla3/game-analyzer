#!/usr/bin/env bash
# Deploy Game Analyzer to Railway (https://railway.app).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if ! command -v railway >/dev/null 2>&1; then
  echo "Installing Railway CLI …"
  brew install railway
fi

if ! railway whoami >/dev/null 2>&1; then
  echo ">>> Log in to Railway:"
  railway login
fi

echo ""
echo "Link or create project (interactive):"
railway link || railway init

if [[ -z "${SECRET_KEY:-}" ]]; then
  export SECRET_KEY="$(openssl rand -hex 32)"
fi
if [[ -z "${INITIAL_ADMIN_PASSWORD:-}" ]]; then
  export INITIAL_ADMIN_PASSWORD="$(openssl rand -base64 18)"
fi
if [[ -z "${PAYMENT_WEBHOOK_SECRET:-}" ]]; then
  export PAYMENT_WEBHOOK_SECRET="$(openssl rand -hex 16)"
fi

echo "Setting variables …"
railway variables set \
  SECRET_KEY="$SECRET_KEY" \
  INITIAL_ADMIN_PASSWORD="$INITIAL_ADMIN_PASSWORD" \
  PAYMENT_WEBHOOK_SECRET="$PAYMENT_WEBHOOK_SECRET" \
  ALLOW_DEMO_ACCOUNTS=true \
  PAYMENT_TEST_MODE=true \
  APP_ENV=production

echo "Deploying (Dockerfile) …"
railway up --detach

echo ""
echo "Generate public domain:"
railway domain || true

echo ""
echo "After deploy:"
echo "  railway open /showcase"
echo "  Set PUBLIC_DEMO_BASE_URL to your Railway URL for /showcase banner"
echo ""
echo "Optional seed on volume (if persistent storage attached):"
echo "  railway run ./scripts/seed_demo.sh"

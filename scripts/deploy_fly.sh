#!/usr/bin/env bash
# Deploy Game Analyzer to Fly.io (interactive: requires `fly auth login` once).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

export PATH="${HOME}/.fly/bin:${PATH}"

if ! command -v fly >/dev/null 2>&1; then
  echo "Installing flyctl to ~/.fly/bin …"
  ARCH="$(uname -m)"
  case "$ARCH" in
    arm64) ASSET="flyctl_0.4.57_macOS_arm64.tar.gz" ;;
    x86_64) ASSET="flyctl_0.4.57_macOS_x86_64.tar.gz" ;;
    *) echo "Unsupported arch: $ARCH"; exit 1 ;;
  esac
  TMP="$(mktemp -d)"
  curl -fsSL -o "$TMP/fly.tgz" "https://github.com/superfly/flyctl/releases/download/v0.4.57/${ASSET}"
  tar xzf "$TMP/fly.tgz" -C "$TMP"
  mkdir -p "${HOME}/.fly/bin"
  mv "$TMP/flyctl" "${HOME}/.fly/bin/flyctl"
  chmod +x "${HOME}/.fly/bin/flyctl"
  ln -sf flyctl "${HOME}/.fly/bin/fly"
  rm -rf "$TMP"
fi

fly version

if ! fly auth whoami >/dev/null 2>&1; then
  echo ""
  echo ">>> 请在浏览器中完成 Fly.io 登录："
  fly auth login
fi

APP_NAME="${FLY_APP_NAME:-game-analyzer-demo}"

app_exists() {
  fly apps list 2>/dev/null | grep -qw "$APP_NAME"
}

if ! app_exists; then
  echo "Creating app $APP_NAME …"
  if ! fly apps create "$APP_NAME" 2>&1 | tee /tmp/fly-apps-create.log; then
    if grep -qi "payment information\|credit card\|buy credit" /tmp/fly-apps-create.log 2>/dev/null; then
      echo ""
      echo "Fly.io 需要绑定支付方式才能创建新应用（即便使用免费额度）。"
      echo "  → 绑定账单: https://fly.io/dashboard (Billing)"
      echo ""
      echo "无需信用卡的替代方案："
      echo "  ./scripts/share_demo.sh     # Cloudflare 临时公网链接（推荐简历 Demo）"
      echo "  docker compose up -d        # 本地 Docker"
      echo "  见 docs/DEPLOY.md § Railway / Render"
      exit 1
    fi
    echo "Failed to create app $APP_NAME"
    exit 1
  fi
fi

if ! app_exists; then
  echo "App $APP_NAME was not created. Aborting."
  exit 1
fi

if ! fly volumes list -a "$APP_NAME" 2>/dev/null | grep -q game_analyzer_data; then
  echo "Creating volume game_analyzer_data (region sin) …"
  fly volumes create game_analyzer_data --region sin --size 1 -a "$APP_NAME" -y
fi

if [[ -z "${SECRET_KEY:-}" ]]; then
  export SECRET_KEY="$(openssl rand -hex 32)"
fi
if [[ -z "${INITIAL_ADMIN_PASSWORD:-}" ]]; then
  export INITIAL_ADMIN_PASSWORD="$(openssl rand -base64 18)"
fi
if [[ -z "${PAYMENT_WEBHOOK_SECRET:-}" ]]; then
  export PAYMENT_WEBHOOK_SECRET="$(openssl rand -hex 16)"
fi

echo "Setting secrets …"
fly secrets set \
  SECRET_KEY="$SECRET_KEY" \
  INITIAL_ADMIN_PASSWORD="$INITIAL_ADMIN_PASSWORD" \
  PAYMENT_WEBHOOK_SECRET="$PAYMENT_WEBHOOK_SECRET" \
  ALLOW_DEMO_ACCOUNTS=true \
  PAYMENT_TEST_MODE=true \
  -a "$APP_NAME"

echo "Deploying …"
fly deploy -a "$APP_NAME"

echo ""
echo "Done. Open:"
echo "  https://${APP_NAME}.fly.dev/showcase"
echo "  https://${APP_NAME}.fly.dev/dashboard  (demo / demo123)"
echo ""
echo "Optional: seed demo data on the volume:"
echo "  fly ssh console -a $APP_NAME -C './scripts/seed_demo.sh'"

#!/usr/bin/env bash
# Pre-deploy validation for production / pilot environments.
# Usage:
#   ./scripts/validate_production_env.sh              # check env only
#   ./scripts/validate_production_env.sh --url https://app.onrender.com
#   APP_ENV=production ALLOW_DEMO_ACCOUNTS=false ./scripts/validate_production_env.sh

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

CHECK_URL=""
FAIL=0
WARN=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --url)
      CHECK_URL="${2:-}"
      shift 2
      ;;
    -h|--help)
      echo "Usage: $0 [--url https://host]"
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

ok() { echo "  OK   $*"; }
warn() { echo "  WARN $*"; WARN=$((WARN + 1)); }
fail() { echo "  FAIL $*"; FAIL=$((FAIL + 1)); }

truthy() {
  case "${1:-}" in
    1|true|yes|on|TRUE|YES|ON) return 0 ;;
    *) return 1 ;;
  esac
}

APP_ENV="${APP_ENV:-development}"
ALLOW_DEMO="${ALLOW_DEMO_ACCOUNTS:-true}"
PAY_TEST="${PAYMENT_TEST_MODE:-}"
SECRET_KEY="${SECRET_KEY:-}"
WEBHOOK="${PAYMENT_WEBHOOK_SECRET:-}"
STRIPE_KEY="${STRIPE_SECRET_KEY:-}"
STRIPE_WH="${STRIPE_WEBHOOK_SECRET:-}"
ADMIN_PW="${INITIAL_ADMIN_PASSWORD:-}"
DATABASE_URL="${DATABASE_URL:-}"

echo "== Game Analyzer production env check =="
echo "APP_ENV=$APP_ENV"

if [[ "$APP_ENV" != "production" ]]; then
  warn "APP_ENV is not production (pilot checks are relaxed)"
fi

if [[ -z "$SECRET_KEY" ]]; then
  if [[ "$APP_ENV" == "production" ]]; then
    fail "SECRET_KEY is empty"
  else
    warn "SECRET_KEY is empty (OK for local dev)"
  fi
elif [[ "$SECRET_KEY" == "dev-secret-key-change-me-before-production" ]]; then
  if [[ "$APP_ENV" == "production" ]]; then
    fail "SECRET_KEY is still the development default"
  else
    warn "SECRET_KEY is development default"
  fi
else
  ok "SECRET_KEY is set"
fi

if truthy "$ALLOW_DEMO" && [[ "$APP_ENV" == "production" ]]; then
  warn "ALLOW_DEMO_ACCOUNTS=true — OK for public demo, not for paid pilot"
else
  ok "Demo accounts policy: ALLOW_DEMO_ACCOUNTS=$ALLOW_DEMO"
fi

if [[ -z "$PAY_TEST" ]]; then
  if [[ "$APP_ENV" == "production" ]]; then
    PAY_TEST="false"
  else
    PAY_TEST="true"
  fi
fi

if truthy "$PAY_TEST"; then
  warn "PAYMENT_TEST_MODE enabled — simulated payment only"
else
  ok "PAYMENT_TEST_MODE is off"
fi

if [[ -n "$WEBHOOK" ]]; then
  ok "PAYMENT_WEBHOOK_SECRET is set (generic HMAC webhook)"
elif [[ -n "$STRIPE_WH" && -n "$STRIPE_KEY" ]]; then
  ok "Stripe keys set (STRIPE_SECRET_KEY + STRIPE_WEBHOOK_SECRET)"
else
  if ! truthy "$PAY_TEST" && [[ "$APP_ENV" == "production" ]]; then
    fail "No payment webhook: set PAYMENT_WEBHOOK_SECRET or Stripe secrets"
  else
    warn "No production webhook configured (acceptable in demo mode)"
  fi
fi

if [[ -n "$STRIPE_KEY" && -z "$STRIPE_WH" ]]; then
  warn "STRIPE_SECRET_KEY set but STRIPE_WEBHOOK_SECRET missing"
fi

if [[ "$APP_ENV" == "production" && -z "$ADMIN_PW" ]]; then
  warn "INITIAL_ADMIN_PASSWORD not set"
else
  ok "Admin bootstrap password policy checked"
fi

if [[ -n "$DATABASE_URL" ]]; then
  ok "DATABASE_URL is set (PostgreSQL)"
elif [[ "$APP_ENV" == "production" ]]; then
  warn "DATABASE_URL not set — production will use SQLite unless config.json overrides"
else
  ok "DATABASE_URL not set (SQLite default for dev)"
fi

if [[ -f "$ROOT/.env" ]]; then
  ok ".env present (local)"
else
  warn "No .env in repo root (cloud deploy may use platform env vars)"
fi

if command -v python3 >/dev/null 2>&1; then
  export PYTHONPATH="${ROOT}/src:${PYTHONPATH:-}"
  if PROFILE="$(PYTHONPATH="${ROOT}/src" python3 -c "from commercial_config import commercial_status_payload; print(commercial_status_payload()['deploy_profile'])" 2>/dev/null)"; then
    ok "commercial_config deploy_profile=$PROFILE"
  else
    warn "Could not import commercial_config (run from repo with PYTHONPATH=src)"
  fi
fi

if [[ -n "$CHECK_URL" ]]; then
  echo ""
  echo "== HTTP checks: $CHECK_URL =="
  HEALTH_URL="${CHECK_URL%/}/api/health"
  STATUS_URL="${CHECK_URL%/}/api/commercial/status"
  if command -v curl >/dev/null 2>&1; then
    if curl -fsS "$HEALTH_URL" -o /tmp/ga-health.json 2>/dev/null; then
      ok "$HEALTH_URL"
      if command -v python3 >/dev/null 2>&1; then
        python3 - <<'PY' /tmp/ga-health.json || fail "health JSON unexpected"
import json, sys
d = json.load(open(sys.argv[1]))
assert d.get("status") == "ok", d
for w in d.get("production_warnings") or []:
    print("  WARN (remote)", w)
PY
      fi
    else
      fail "Could not reach $HEALTH_URL"
    fi
    if curl -fsS "$STATUS_URL" -o /tmp/ga-commercial.json 2>/dev/null; then
      ok "$STATUS_URL"
    else
      fail "Could not reach $STATUS_URL"
    fi
    if curl -fsS "${CHECK_URL%/}/trust" -o /dev/null 2>/dev/null; then
      ok "${CHECK_URL%/}/trust"
    else
      fail "Could not reach /trust"
    fi
  else
    warn "curl not installed — skipping HTTP checks"
  fi
fi

echo ""
echo "Summary: $FAIL failure(s), $WARN warning(s)"
if [[ "$FAIL" -gt 0 ]]; then
  echo "Fix failures before paid pilot. See docs/COMMERCIAL_LAUNCH.md"
  exit 1
fi
exit 0

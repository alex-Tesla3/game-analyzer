#!/usr/bin/env bash
# Set GitHub repo metadata (topics, description, homepage) for portfolio visibility.
set -euo pipefail

REPO="${GITHUB_REPO:-alex-Tesla3/game-analyzer}"
HOMEPAGE="${PUBLIC_DEMO_BASE_URL:-}"

if ! gh auth status >/dev/null 2>&1; then
  echo "Run: gh auth login"
  exit 1
fi

if [[ -z "$HOMEPAGE" && -f /tmp/game-analyzer-tunnel.url ]]; then
  HOMEPAGE="$(cat /tmp/game-analyzer-tunnel.url)"
fi

echo "Updating ${REPO} …"
gh repo edit "$REPO" \
  --description "Full-stack game BI & competitor intelligence — Steam/TapTap/Google Play crawl → dashboard · FastAPI · pytest · Playwright CI" \
  --add-topic fastapi --add-topic python --add-topic playwright \
  --add-topic sqlite --add-topic dashboard --add-topic game-analytics \
  --add-topic pytest --add-topic docker

if [[ -n "$HOMEPAGE" ]]; then
  gh repo edit "$REPO" --homepage "${HOMEPAGE%/}/showcase"
  echo "Homepage: ${HOMEPAGE%/}/showcase"
fi

echo "Done: https://github.com/${REPO}"

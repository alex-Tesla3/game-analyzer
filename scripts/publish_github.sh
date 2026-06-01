#!/usr/bin/env bash
# Export game_analyzer as a standalone git repo and push to GitHub.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REPO_NAME="${GITHUB_REPO_NAME:-game-analyzer}"
EXPORT_DIR="${GITHUB_EXPORT_DIR:-${HOME}/Projects/${REPO_NAME}}"
GITHUB_USER="${GITHUB_USER:-}"
GITHUB_PUSH="${GITHUB_PUSH:-true}"

usage() {
  cat <<EOF
Usage: GITHUB_USER=<your-gh-username> ./scripts/publish_github.sh

Optional env:
  GITHUB_REPO_NAME   default: game-analyzer
  GITHUB_EXPORT_DIR  default: ~/Projects/game-analyzer
  GITHUB_VISIBILITY  public (default) | private
  GITHUB_PUSH        true (default) | false

Requires: git. GitHub push mode also requires gh (brew install gh && gh auth login).
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ "$GITHUB_PUSH" != "false" && -z "$GITHUB_USER" ]]; then
  if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
    GITHUB_USER="$(gh api user -q .login)"
  fi
fi

if [[ "$GITHUB_PUSH" != "false" && -z "$GITHUB_USER" ]]; then
  echo "Set GITHUB_USER=your-github-username or run: gh auth login"
  exit 1
fi

if [[ "$GITHUB_PUSH" != "false" ]] && ! command -v gh >/dev/null 2>&1; then
  echo "Installing GitHub CLI (gh) …"
  brew install gh
fi

if [[ "$GITHUB_PUSH" != "false" ]] && ! gh auth status >/dev/null 2>&1; then
  echo ">>> Log in to GitHub:"
  gh auth login
fi

VIS="${GITHUB_VISIBILITY:-public}"
mkdir -p "$(dirname "$EXPORT_DIR")"

echo "Exporting to ${EXPORT_DIR} …"
rsync -a --delete \
  --exclude '.venv/' \
  --exclude 'venv/' \
  --exclude '__pycache__/' \
  --exclude '*.pyc' \
  --exclude '.pytest_cache/' \
  --exclude '.DS_Store' \
  --exclude 'output.jsonl' \
  --exclude 'data/game_analyzer.db' \
  --exclude 'data/game_analyzer.db-*' \
  --exclude '.env' \
  "$ROOT/" "$EXPORT_DIR/"

cd "$EXPORT_DIR"

if [[ ! -f LICENSE ]]; then
  cat > LICENSE <<'LICENSE_EOF'
MIT License

Copyright (c) 2026 Game Analyzer contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
LICENSE_EOF
fi

if [[ ! -d .git ]]; then
  git init -b main
fi

git add -A
if git diff --cached --quiet; then
  echo "No changes to commit."
else
  git commit -m "$(cat <<EOF
Initial portfolio export: Game Analyzer full-stack BI platform.

FastAPI + vanilla JS dashboard, pytest CI, showcase page, and deploy docs.
EOF
)"
fi

if [[ "$GITHUB_PUSH" == "false" ]]; then
  echo ""
  echo "Local export ready: ${EXPORT_DIR}"
  echo "Skipping GitHub push because GITHUB_PUSH=false."
  exit 0
fi

REMOTE="https://github.com/${GITHUB_USER}/${REPO_NAME}.git"
if ! gh repo view "${GITHUB_USER}/${REPO_NAME}" >/dev/null 2>&1; then
  echo "Creating GitHub repo ${GITHUB_USER}/${REPO_NAME} (${VIS}) …"
  gh repo create "${REPO_NAME}" \
    --"${VIS}" \
    --source=. \
    --remote=origin \
    --description "Full-stack game BI & competitor intelligence platform (FastAPI, pytest, Playwright)" \
    --push
else
  git remote remove origin 2>/dev/null || true
  git remote add origin "$REMOTE"
  git push -u origin main
fi

DEMO_URL="${PUBLIC_DEMO_BASE_URL:-}"
if [[ -n "$DEMO_URL" ]]; then
  gh repo edit "${GITHUB_USER}/${REPO_NAME}" --homepage "${DEMO_URL}/showcase" || true
fi

echo ""
echo "Done: https://github.com/${GITHUB_USER}/${REPO_NAME}"
echo "Set homepage after deploy: gh repo edit ${GITHUB_USER}/${REPO_NAME} --homepage https://your-demo/showcase"

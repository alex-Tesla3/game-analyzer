#!/usr/bin/env bash
# Start Postgres in Docker, run the app locally (no Docker image build).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

export DATABASE_URL="${DATABASE_URL:-postgresql://game:game@127.0.0.1:5432/game_analyzer}"

echo "Starting Postgres (Docker)..."
docker compose -f docker-compose.postgres-only.yml up -d

echo "Waiting for Postgres..."
for i in $(seq 1 30); do
  if docker compose -f docker-compose.postgres-only.yml exec -T postgres pg_isready -U game -d game_analyzer >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

if [[ "${RUN_MIGRATE:-}" == "1" ]]; then
  echo "Migrating SQLite → Postgres (optional)..."
  PYTHONPATH=src "${ROOT}/.venv/bin/python" scripts/migrate_sqlite_to_postgres.py || true
fi

echo "DATABASE_URL=$DATABASE_URL"
echo "Starting app on host..."
exec "$ROOT/scripts/dev.sh"

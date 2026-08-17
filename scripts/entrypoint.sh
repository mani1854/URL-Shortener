#!/usr/bin/env bash
# scripts/entrypoint.sh
#
# Docker entrypoint script.
# 1. Waits for PostgreSQL to be ready.
# 2. Runs any pending Alembic migrations.
# 3. Starts the Uvicorn server.

set -euo pipefail

echo "[entrypoint] Waiting for PostgreSQL at ${POSTGRES_SERVER}:${POSTGRES_PORT:-5432}..."

until pg_isready -h "${POSTGRES_SERVER}" -p "${POSTGRES_PORT:-5432}" -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -q; do
    echo "[entrypoint] Postgres is not ready yet, sleeping 1s..."
    sleep 1
done

echo "[entrypoint] PostgreSQL is ready."

echo "[entrypoint] Running Alembic migrations..."
alembic upgrade head
echo "[entrypoint] Migrations complete."

echo "[entrypoint] Starting Uvicorn..."
exec uvicorn main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers "${UVICORN_WORKERS:-1}" \
    --log-level "${LOG_LEVEL:-info}" \
    --proxy-headers \
    --forwarded-allow-ips="*"

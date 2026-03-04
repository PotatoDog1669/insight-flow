#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
VENV_BIN="$ROOT_DIR/.venv/bin"

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "[dev-local] Missing command: $1"
    exit 1
  fi
}

require_cmd docker
require_cmd npm

if [ ! -x "$VENV_BIN/python" ]; then
  echo "[dev-local] Missing Python venv at $VENV_BIN"
  echo "Create it first, e.g.: python3 -m venv .venv"
  exit 1
fi

# Load project .env first so dev-local and docker compose share one source of truth.
if [ -f "$ROOT_DIR/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.env"
  set +a
fi

DB_PASSWORD_VALUE="${DB_PASSWORD:-password}"
export DB_PASSWORD="$DB_PASSWORD_VALUE"
export DATABASE_URL="${DATABASE_URL:-postgresql+asyncpg://lex:${DB_PASSWORD_VALUE}@localhost:5432/lexdeepresearch}"

if [ ! -x "$VENV_BIN/uvicorn" ]; then
  echo "[dev-local] Missing uvicorn in .venv"
  echo "Run: make backend-deps"
  exit 1
fi

if [ ! -x "$VENV_BIN/alembic" ]; then
  echo "[dev-local] Missing alembic in .venv"
  echo "Run: make backend-deps"
  exit 1
fi

cleanup() {
  if [ -n "${BACKEND_PID:-}" ] && kill -0 "$BACKEND_PID" >/dev/null 2>&1; then
    kill "$BACKEND_PID" >/dev/null 2>&1 || true
  fi
}

wait_for_postgres() {
  echo "[dev-local] Waiting for postgres to accept connections..."
  local ready=0
  for _ in $(seq 1 60); do
    if DATABASE_URL="$DATABASE_URL" "$VENV_BIN/python" - <<'PY' >/dev/null 2>&1
import asyncio
import os
import sys

import asyncpg


async def _check() -> None:
    url = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://", 1)
    conn = await asyncpg.connect(url, timeout=3, ssl=False)
    await conn.close()


try:
    asyncio.run(_check())
except Exception:
    sys.exit(1)
PY
    then
      ready=1
      break
    fi
    sleep 1
  done

  if [ "$ready" -ne 1 ]; then
    echo "[dev-local] Postgres did not accept connections within 60s"
    docker compose logs postgres | tail -n 120 || true
    return 1
  fi
  return 0
}

trap cleanup EXIT INT TERM

echo "[dev-local] Starting infra (postgres, redis)..."
cd "$ROOT_DIR"
docker compose up -d postgres redis

wait_for_postgres

echo "[dev-local] Running migrations..."
cd "$BACKEND_DIR"

run_migrate() {
  PYTHONPATH=. "$VENV_BIN/alembic" upgrade head
}

MIGRATED=0
for i in $(seq 1 5); do
  if run_migrate; then
    MIGRATED=1
    break
  fi
  echo "[dev-local] Migration attempt $i failed, retrying in 2s..."
  sleep 2
done

if [ "$MIGRATED" -ne 1 ]; then
  TMP_LOG="$(mktemp)"
  if ! run_migrate >"$TMP_LOG" 2>&1; then
    if grep -q "InvalidPasswordError" "$TMP_LOG"; then
      echo "[dev-local] Detected postgres password mismatch. Recreating local postgres volume..."
      cd "$ROOT_DIR"
      docker compose down -v
      docker compose up -d postgres redis
      wait_for_postgres
      cd "$BACKEND_DIR"
      if ! run_migrate; then
        echo "[dev-local] Migration failed even after resetting postgres volume"
        cat "$TMP_LOG"
        rm -f "$TMP_LOG"
        exit 1
      fi
    else
      echo "[dev-local] Migration failed after retries"
      cat "$TMP_LOG"
      rm -f "$TMP_LOG"
      exit 1
    fi
  fi
  rm -f "$TMP_LOG"
fi

echo "[dev-local] Starting backend on :8000..."
PYTHONPATH=. "$VENV_BIN/uvicorn" app.main:app --reload --port 8000 &
BACKEND_PID=$!

sleep 1

echo "[dev-local] Starting frontend on :3000..."
cd "$FRONTEND_DIR"
npm run dev

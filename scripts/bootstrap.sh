#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
VENV_PY="$ROOT_DIR/.venv/bin/python"

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "[bootstrap] missing command: $1"
    exit 1
  fi
}

run_pip_with_fallback() {
  local args=("$@")
  local configured_index=""
  configured_index="$("$VENV_PY" -m pip config get global.index-url 2>/dev/null || true)"

  local indexes=()
  if [ -n "${PIP_INDEX_URL:-}" ]; then
    indexes+=("${PIP_INDEX_URL}")
  fi
  if [ -n "$configured_index" ]; then
    indexes+=("$configured_index")
  fi
  indexes+=("https://pypi.org/simple" "https://pypi.tuna.tsinghua.edu.cn/simple")

  local attempted=""
  for idx in "${indexes[@]}"; do
    if [ "x$idx" = "x$attempted" ]; then
      continue
    fi
    attempted="$idx"
    local host
    host="$("$VENV_PY" - "$idx" <<'PY'
import sys
from urllib.parse import urlparse
print(urlparse(sys.argv[1]).hostname or "")
PY
)"
    echo "[bootstrap] pip index => $idx"
    if PIP_INDEX_URL="$idx" PIP_TRUSTED_HOST="$host" "$VENV_PY" -m pip "${args[@]}"; then
      return 0
    fi
    echo "[bootstrap] pip command failed on $idx, trying next index..."
  done

  return 1
}

echo "[bootstrap] checking prerequisites..."
require_cmd python3
require_cmd npm
require_cmd docker

if [ ! -f "$ROOT_DIR/.env" ] && [ -f "$ROOT_DIR/.env.example" ]; then
  cp "$ROOT_DIR/.env.example" "$ROOT_DIR/.env"
  echo "[bootstrap] created .env from .env.example"
fi

if [ ! -x "$VENV_PY" ]; then
  echo "[bootstrap] creating .venv..."
  python3 -m venv "$ROOT_DIR/.venv"
fi

if [ ! -x "$ROOT_DIR/.venv/bin/pip" ] && [ ! -x "$ROOT_DIR/.venv/bin/pip3" ]; then
  echo "[bootstrap] repairing pip via ensurepip..."
  "$VENV_PY" -m ensurepip --upgrade
fi

echo "[bootstrap] upgrading base python tooling..."
run_pip_with_fallback install -U pip setuptools wheel

echo "[bootstrap] installing backend deps..."
cd "$BACKEND_DIR"
run_pip_with_fallback install -e ".[dev]"

echo "[bootstrap] installing frontend deps..."
cd "$FRONTEND_DIR"
if ! npm ci; then
  echo "[bootstrap] npm ci failed, isolating existing node_modules and retrying npm install..."
  if [ -d "$FRONTEND_DIR/node_modules" ]; then
    mv "$FRONTEND_DIR/node_modules" "$FRONTEND_DIR/node_modules.bak.$(date +%s)"
  fi
  npm install
fi

echo "[bootstrap] done"
echo "[bootstrap] next: make doctor && make infra-up && make migrate && make dev-local"

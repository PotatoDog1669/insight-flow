#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PY="$ROOT_DIR/.venv/bin/python"

FAILURES=0
WARNINGS=0

ok() {
  echo "[doctor][ok] $1"
}

warn() {
  WARNINGS=$((WARNINGS + 1))
  echo "[doctor][warn] $1"
}

fail() {
  FAILURES=$((FAILURES + 1))
  echo "[doctor][fail] $1"
}

check_cmd() {
  local name="$1"
  if command -v "$name" >/dev/null 2>&1; then
    ok "command available: $name"
  else
    fail "missing command: $name"
  fi
}

check_port() {
  local port="$1"
  if ! command -v ss >/dev/null 2>&1; then
    warn "ss not available, skip port check for :$port"
    return
  fi
  local line
  line="$(ss -ltnp 2>/dev/null | awk -v p=":$port" '$4 ~ p || $5 ~ p {print; exit}')"
  if [ -n "$line" ]; then
    warn "port :$port already in use"
  else
    ok "port :$port is free"
  fi
}

echo "[doctor] checking local prerequisites..."
check_cmd python3
check_cmd npm
check_cmd docker

if docker info >/dev/null 2>&1; then
  ok "docker daemon is reachable"
else
  fail "docker daemon is not reachable"
fi

if [ -f "$ROOT_DIR/.env" ]; then
  ok ".env exists"
else
  warn ".env not found (run: cp .env.example .env)"
fi

if [ -x "$VENV_PY" ]; then
  ok ".venv python exists"
else
  fail ".venv python missing (run: make bootstrap)"
fi

if [ -x "$ROOT_DIR/.venv/bin/pip" ] || [ -x "$ROOT_DIR/.venv/bin/pip3" ]; then
  ok ".venv pip exists"
else
  fail ".venv pip missing (run: make bootstrap)"
fi

if [ -x "$ROOT_DIR/.venv/bin/uvicorn" ] || [ -x "$ROOT_DIR/.venv/bin/python" ]; then
  ok "backend runtime entrypoints look present"
else
  fail "backend runtime tools missing (run: make bootstrap)"
fi

if [ -x "$VENV_PY" ]; then
  INDEX_URL="${PIP_INDEX_URL:-$("$VENV_PY" -m pip config get global.index-url 2>/dev/null || true)}"
  if [ -n "$INDEX_URL" ]; then
    if "$VENV_PY" - "$INDEX_URL" <<'PY'
import socket
import sys
from urllib.parse import urlparse

url = sys.argv[1]
host = urlparse(url).hostname or ""
if not host:
    raise SystemExit(1)
socket.gethostbyname(host)
PY
    then
      ok "pip index host resolvable: $INDEX_URL"
    else
      warn "pip index host not resolvable: $INDEX_URL"
    fi
  else
    warn "no explicit pip index-url configured"
  fi
fi

check_port 8000
check_port 3000

if [ "$FAILURES" -gt 0 ]; then
  echo "[doctor] completed with $FAILURES failure(s), $WARNINGS warning(s)"
  exit 1
fi

echo "[doctor] completed with $WARNINGS warning(s), no blocking failures"

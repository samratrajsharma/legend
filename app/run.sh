#!/usr/bin/env bash
# Know Your Code — start backend + frontend (macOS / Linux; the run.ps1 counterpart).
#
#   ./run.sh              start normally
#   ./run.sh --fresh      wipe ALL indexed repos, caches and timeline history, then start
#   ./run.sh --fresh -y   same, without the confirmation prompt
#   ./run.sh --reload     backend hot-reload (KNOWIT_RELOAD=1) — see main.py for why it's off by default
#
# --fresh does NOT touch .env (API keys), node_modules, or the Python env.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"

FRESH=0; RELOAD=0; YES=0
for arg in "$@"; do
  case "$arg" in
    --fresh)     FRESH=1 ;;
    --reload)    RELOAD=1 ;;
    -y|--yes)    YES=1 ;;
    -h|--help)   sed -n '2,9p' "$0"; exit 0 ;;
    *) echo "Unknown option: $arg (try --help)" >&2; exit 2 ;;
  esac
done

# ----- data dir the backend uses: $KNOWIT_DATA_DIR > backend/.env > backend/.cache -----
resolve_data_dir() {
  local v="${KNOWIT_DATA_DIR:-}"
  if [ -z "$v" ] && [ -f "$BACKEND/.env" ]; then
    v="$(sed -nE 's/^[[:space:]]*KNOWIT_DATA_DIR[[:space:]]*=[[:space:]]*//p' "$BACKEND/.env" | head -1)"
    v="${v%\"}"; v="${v#\"}"; v="${v%\'}"; v="${v#\'}"
  fi
  [ -z "$v" ] && v="$BACKEND/.cache"
  case "$v" in /*) : ;; *) v="$BACKEND/$v" ;; esac
  printf '%s' "$v"
}
DATA_DIR="$(resolve_data_dir)"

# ----- --fresh : start from a clean slate -----
if [ "$FRESH" = 1 ]; then
  echo "[fresh] Data directory: $DATA_DIR"
  if [ -d "$DATA_DIR" ]; then
    echo "[fresh] This permanently deletes cloned repos, indexes, vector store, snapshots and timeline history."
    echo "[fresh] Keeps: .env (API keys), node_modules, Python env."
    if [ "$YES" != 1 ]; then
      read -r -p "Type 'yes' to wipe and start fresh: " ans
      [ "$ans" = "yes" ] || { echo "[fresh] Aborted. Nothing deleted."; exit 1; }
    fi
    rm -rf "$DATA_DIR"
    echo "[fresh] Wiped."
  else
    echo "[fresh] Already clean."
  fi
fi

# ----- pick a Python interpreter: active conda/venv, else a local backend/.venv -----
if [ -n "${CONDA_DEFAULT_ENV:-}" ] || [ -n "${VIRTUAL_ENV:-}" ]; then
  PY="python"
  echo "[setup] Using the active Python environment."
else
  VENV="$BACKEND/.venv"
  if [ ! -x "$VENV/bin/python" ]; then
    echo "[setup] Creating Python venv at $VENV"
    python3 -m venv "$VENV"
  fi
  PY="$VENV/bin/python"
fi

# ----- backend deps: (re)install if the core packages aren't importable -----
if ! "$PY" -c "import fastapi, uvicorn, pydantic, dotenv" >/dev/null 2>&1; then
  echo "[setup] Installing backend Python packages..."
  "$PY" -m pip install --upgrade pip >/dev/null
  "$PY" -m pip install -r "$BACKEND/requirements.txt"
  touch "$BACKEND/.deps-installed"
else
  echo "[setup] Backend deps already installed and importable."
fi

# ----- .env on first run -----
if [ ! -f "$BACKEND/.env" ] && [ -f "$BACKEND/.env.example" ]; then
  cp "$BACKEND/.env.example" "$BACKEND/.env"
fi

# ----- frontend deps -----
if [ ! -d "$FRONTEND/node_modules" ]; then
  echo "[setup] Installing npm packages (first run only)..."
  ( cd "$FRONTEND" && npm install )
else
  echo "[setup] Frontend deps already installed (delete 'node_modules' to force reinstall)."
fi

echo
echo "Starting Know Your Code..."
echo "  Backend:  http://localhost:8100  (docs at /docs)"
echo "  Frontend: http://localhost:5273"
[ "$RELOAD" = 1 ] && echo "  Backend hot-reload: ON"
echo "  Press Ctrl+C to stop both."
echo

if [ "$RELOAD" = 1 ]; then export KNOWIT_RELOAD=1; else export KNOWIT_RELOAD=0; fi

BACK_PID=""; FRONT_PID=""
cleanup() {
  echo; echo "Stopping Know Your Code..."
  [ -n "$FRONT_PID" ] && kill "$FRONT_PID" 2>/dev/null || true
  [ -n "$BACK_PID" ]  && kill "$BACK_PID"  2>/dev/null || true
}
trap cleanup INT TERM EXIT

( cd "$BACKEND"  && exec "$PY" main.py ) & BACK_PID=$!
sleep 2
( cd "$FRONTEND" && exec npm run dev ) & FRONT_PID=$!
wait

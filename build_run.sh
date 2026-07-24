#!/usr/bin/env bash
# =============================================================================
#  FlowForge — Build + Run (build_run.sh)
#  Builds backend (venv + pip) and frontend (npm install + next build),
#  frees ports 8000 / 3000, then starts both servers.
#  Usage:  ./build_run.sh [--no-build]   (--no-build skips install/build steps)
# =============================================================================
set -euo pipefail

# ── Resolve paths ─────────────────────────────────────────────────────────────
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="${ROOT_DIR}/backend"
FRONTEND_DIR="${ROOT_DIR}/frontend"

BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"
BACKEND_HOST="${BACKEND_HOST:-0.0.0.0}"
FRONTEND_HOST="${FRONTEND_HOST:-0.0.0.0}"

SKIP_BUILD=false
if [[ "${1:-}" == "--no-build" ]]; then
  SKIP_BUILD=true
fi

# ── Helpers ───────────────────────────────────────────────────────────────────
log()     { echo -e "\033[1;36m[FlowForge]\033[0m $*"; }
success() { echo -e "\033[1;32m[FlowForge]\033[0m $*"; }
warn()    { echo -e "\033[1;33m[FlowForge]\033[0m $*"; }
err()     { echo -e "\033[1;31m[FlowForge]\033[0m $*" >&2; }

free_port() {
  local port=$1
  if fuser "${port}/tcp" &>/dev/null 2>&1; then
    warn "Port ${port} is occupied — killing existing process..."
    fuser -k "${port}/tcp" 2>/dev/null || true
    sleep 0.8
    success "Port ${port} freed."
  else
    log "Port ${port} is free."
  fi
}

# ── Shutdown handler (runs exactly once) ────────────────────────────────────
_SHUTDOWN=false
_shutdown() {
  # Guard against re-entrant calls (EXIT fires after INT/TERM kills the script)
  if [[ "${_SHUTDOWN}" == true ]]; then return; fi
  _SHUTDOWN=true
  echo ""
  warn "Shutting down — stopping backend and frontend..."
  # Kill tracked PIDs gracefully first, then force
  [[ -n "${BACKEND_PID:-}"  ]] && kill "${BACKEND_PID}"  2>/dev/null || true
  [[ -n "${FRONTEND_PID:-}" ]] && kill "${FRONTEND_PID}" 2>/dev/null || true
  sleep 1
  [[ -n "${BACKEND_PID:-}"  ]] && kill -9 "${BACKEND_PID}"  2>/dev/null || true
  [[ -n "${FRONTEND_PID:-}" ]] && kill -9 "${FRONTEND_PID}" 2>/dev/null || true
  success "All servers stopped. Goodbye."
}
trap '_shutdown' INT TERM
trap '_shutdown' EXIT

# ── Banner ────────────────────────────────────────────────────────────────────
echo ""
echo "  ╔══════════════════════════════════════════════╗"
echo "  ║    FlowForge Control Plane — Build & Run     ║"
echo "  ╚══════════════════════════════════════════════╝"
echo ""

# ── Load shared .env ──────────────────────────────────────────────────────────
if [[ -f "${ROOT_DIR}/.env" ]]; then
  log "Loading .env from project root..."
  set -a
  # shellcheck disable=SC1091
  source "${ROOT_DIR}/.env"
  set +a
fi

# ═════════════════════════════════════════════════════════════════════════════
#  STEP 1 — Build Backend
# ═════════════════════════════════════════════════════════════════════════════
if [[ "${SKIP_BUILD}" == false ]]; then
  log "━━━ [1/4] Building Python backend ━━━"
  cd "${BACKEND_DIR}"

  if [[ ! -d .venv ]]; then
    log "Creating Python virtualenv at backend/.venv ..."
    python3 -m venv .venv
  fi

  # shellcheck disable=SC1091
  source .venv/bin/activate
  pip install --upgrade pip -q
  pip install -r requirements.txt -q
  success "Backend dependencies installed."
  deactivate 2>/dev/null || true
  cd "${ROOT_DIR}"
else
  warn "Skipping backend build (--no-build)."
fi

# ═════════════════════════════════════════════════════════════════════════════
#  STEP 2 — Build Frontend
# ═════════════════════════════════════════════════════════════════════════════
if [[ "${SKIP_BUILD}" == false ]]; then
  log "━━━ [2/4] Building Next.js frontend ━━━"
  cd "${FRONTEND_DIR}"

  if [[ ! -d node_modules ]]; then
    log "Installing npm dependencies..."
    npm install
  fi

  log "Running next build..."
  npm run build
  success "Frontend build complete."
  cd "${ROOT_DIR}"
else
  warn "Skipping frontend build (--no-build)."
fi

# ═════════════════════════════════════════════════════════════════════════════
#  STEP 3 — Free ports
# ═════════════════════════════════════════════════════════════════════════════
log "━━━ [3/4] Releasing ports ━━━"
free_port "${BACKEND_PORT}"
free_port "${FRONTEND_PORT}"

# ═════════════════════════════════════════════════════════════════════════════
#  STEP 4 — Start servers
# ═════════════════════════════════════════════════════════════════════════════
log "━━━ [4/4] Starting servers ━━━"

# — Backend (FastAPI / Uvicorn) ————————————————————————————————————————————
log "Starting FastAPI backend  →  http://${BACKEND_HOST}:${BACKEND_PORT}"
cd "${BACKEND_DIR}"
# shellcheck disable=SC1091
source .venv/bin/activate
PYTHONPATH="${BACKEND_DIR}" \
  uvicorn app.main:app \
    --host "${BACKEND_HOST}" \
    --port "${BACKEND_PORT}" \
    --reload \
    2>&1 | sed 's/^/  [backend] /' &
BACKEND_PID=$!
cd "${ROOT_DIR}"

# Give Uvicorn a moment to bind before starting the frontend
sleep 2

# — Frontend (Next.js dev) ————————————————————————————————————————————————
log "Starting Next.js frontend  →  http://${FRONTEND_HOST}:${FRONTEND_PORT}"
cd "${FRONTEND_DIR}"
npm run dev -- --hostname "${FRONTEND_HOST}" --port "${FRONTEND_PORT}" \
  2>&1 | sed 's/^/  [frontend] /' &
FRONTEND_PID=$!
cd "${ROOT_DIR}"

# ── Ready banner ─────────────────────────────────────────────────────────────
sleep 3
echo ""
echo "  ╔══════════════════════════════════════════════╗"
echo "  ║          FlowForge is running! 🚀            ║"
echo "  ║                                              ║"
printf  "  ║  Frontend  →  http://localhost:%-5s        ║\n" "${FRONTEND_PORT}"
printf  "  ║  Backend   →  http://localhost:%-5s        ║\n" "${BACKEND_PORT}"
printf  "  ║  API Docs  →  http://localhost:%-5s/docs   ║\n" "${BACKEND_PORT}"
echo "  ║                                              ║"
echo "  ║  Press Ctrl-C to stop both servers           ║"
echo "  ╚══════════════════════════════════════════════╝"
echo ""

# Wait for both processes
wait "${BACKEND_PID}" "${FRONTEND_PID}"

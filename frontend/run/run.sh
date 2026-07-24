#!/usr/bin/env bash
# Run LoopForge Next.js frontend (dev server)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
ROOT_DIR="$(cd "${FRONTEND_DIR}/.." && pwd)"

cd "${FRONTEND_DIR}"

if [[ ! -d node_modules ]]; then
  echo "Installing frontend dependencies..."
  npm install
fi

# Load shared monorepo env so Next rewrites can read LOOPFORGE_API_ORIGIN
if [[ -f "${ROOT_DIR}/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${ROOT_DIR}/.env"
  set +a
fi

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-3000}"

echo "Starting LoopForge UI on http://localhost:${PORT}"
echo "API proxy target: ${LOOPFORGE_API_ORIGIN:-http://127.0.0.1:8000}"
exec npm run dev -- --hostname "${HOST}" --port "${PORT}"

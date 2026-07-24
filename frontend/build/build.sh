#!/usr/bin/env bash
# Build LoopForge Next.js frontend (production bundle)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
ROOT_DIR="$(cd "${FRONTEND_DIR}/.." && pwd)"

cd "${FRONTEND_DIR}"

echo "Building frontend at ${FRONTEND_DIR}"

if [[ ! -d node_modules ]]; then
  echo "Installing frontend dependencies..."
  npm install
fi

if [[ -f "${ROOT_DIR}/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${ROOT_DIR}/.env"
  set +a
fi

npm run build

echo "Frontend build complete."
echo "Start production server with: cd ${FRONTEND_DIR} && npm start"
echo "Or use dev mode:            ${FRONTEND_DIR}/run/run.sh"

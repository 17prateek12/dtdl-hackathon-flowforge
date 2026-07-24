#!/usr/bin/env bash
# Build / prepare LoopForge Python backend (venv + dependencies)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${BACKEND_DIR}"

echo "Building backend at ${BACKEND_DIR}"

if [[ ! -d .venv ]]; then
  echo "Creating virtualenv..."
  python3 -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt

echo "Backend build complete."
echo "Activate with: source ${BACKEND_DIR}/.venv/bin/activate"
echo "Or run with:   ${BACKEND_DIR}/run/run.sh"

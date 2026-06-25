#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
REQUIREMENTS="${REQUIREMENTS:-$SCRIPT_DIR/requirements-ai-studio.txt}"
WHEELHOUSE="${WHEELHOUSE:-$SCRIPT_DIR/wheelhouse}"
VENV_DIR="${VENV_DIR:-.venv}"

if [ ! -d "$WHEELHOUSE" ] || ! find "$WHEELHOUSE" -maxdepth 1 -type f \( -name '*.whl' -o -name '*.tar.gz' -o -name '*.zip' \) | grep -q .; then
  echo "Missing wheelhouse files: $WHEELHOUSE" >&2
  echo "Run download_wheels.sh in an online WSL environment first, then copy .opencode/wsl/wheelhouse into the closed network." >&2
  exit 1
fi

if [ ! -d "$VENV_DIR" ]; then
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

python -m pip install --no-index --find-links "$WHEELHOUSE" --requirement "$REQUIREMENTS"

echo "Offline install complete using: $WHEELHOUSE"

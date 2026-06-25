#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
REQUIREMENTS="${REQUIREMENTS:-$SCRIPT_DIR/requirements-ai-studio.txt}"
WHEELHOUSE="${WHEELHOUSE:-$SCRIPT_DIR/wheelhouse}"

mkdir -p "$WHEELHOUSE"

"$PYTHON_BIN" -m pip download \
  --dest "$WHEELHOUSE" \
  --requirement "$REQUIREMENTS"

echo "Wheelhouse ready: $WHEELHOUSE"

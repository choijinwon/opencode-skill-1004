#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
REQUIREMENTS="${REQUIREMENTS:-$SCRIPT_DIR/requirements-ai-studio.txt}"
WHEELHOUSE="${WHEELHOUSE:-$SCRIPT_DIR/wheelhouse}"

mkdir -p "$WHEELHOUSE"

reject_https_url() {
  local name="$1"
  local value="${2:-}"
  if [[ "$value" == https://* ]]; then
    echo "SSL is not allowed: $name uses https://." >&2
    echo "Use an internal HTTP mirror, for example: export PIP_INDEX_URL=http://<internal-pypi>/simple" >&2
    echo "For a Nexus PyTorch CPU proxy upstream, use: https://download.pytorch.org/whl/cpu" >&2
    echo "Or copy wheel files into $WHEELHOUSE manually and run install_offline.sh." >&2
    exit 1
  fi
}

trusted_host_from_url() {
  local value="$1"
  local host="${value#http://}"
  host="${host%%/*}"
  host="${host%%:*}"
  printf '%s' "$host"
}

INDEX_ARGS=()
if [[ -n "${PIP_INDEX_URL:-}" ]]; then
  reject_https_url "PIP_INDEX_URL" "$PIP_INDEX_URL"
  INDEX_ARGS+=(--index-url "$PIP_INDEX_URL")
  if [[ "$PIP_INDEX_URL" == http://* ]]; then
    INDEX_ARGS+=(--trusted-host "$(trusted_host_from_url "$PIP_INDEX_URL")")
  fi
elif [[ -z "${PIP_EXTRA_INDEX_URL:-}" ]]; then
  echo "SSL is not allowed and the default pip index uses HTTPS." >&2
  echo "Set an internal HTTP mirror first:" >&2
  echo "  export PIP_INDEX_URL=http://<internal-pypi>/simple" >&2
  echo "PyTorch CPU Nexus upstream reference:" >&2
  echo "  https://download.pytorch.org/whl/cpu" >&2
  echo "Then run this script again, or manually copy wheels into:" >&2
  echo "  $WHEELHOUSE" >&2
  exit 1
fi

if [[ -n "${PIP_EXTRA_INDEX_URL:-}" ]]; then
  reject_https_url "PIP_EXTRA_INDEX_URL" "$PIP_EXTRA_INDEX_URL"
  INDEX_ARGS+=(--extra-index-url "$PIP_EXTRA_INDEX_URL")
  if [[ "$PIP_EXTRA_INDEX_URL" == http://* ]]; then
    INDEX_ARGS+=(--trusted-host "$(trusted_host_from_url "$PIP_EXTRA_INDEX_URL")")
  fi
fi

if [[ -n "${PIP_TRUSTED_HOST:-}" ]]; then
  INDEX_ARGS+=(--trusted-host "$PIP_TRUSTED_HOST")
fi

"$PYTHON_BIN" -m pip --isolated download \
  "${INDEX_ARGS[@]}" \
  --dest "$WHEELHOUSE" \
  --requirement "$REQUIREMENTS"

echo "Wheelhouse ready: $WHEELHOUSE"

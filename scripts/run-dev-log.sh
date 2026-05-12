#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEMP_DIR="$ROOT_DIR/temp"
LOG_FILE="$TEMP_DIR/app_log.txt"

mkdir -p "$TEMP_DIR"

cd "$ROOT_DIR"

if [[ -f "$ROOT_DIR/.venv-1/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.venv-1/bin/activate"
fi

echo "Starting app, logging to $LOG_FILE"
python web/app.py > "$LOG_FILE" 2>&1

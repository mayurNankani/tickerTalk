#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TEMP_DIR="$ROOT_DIR/temp"
COOKIE_FILE="$TEMP_DIR/cookies.txt"
RESPONSE_FILE="$TEMP_DIR/response.json"

mkdir -p "$TEMP_DIR"
rm -f "$COOKIE_FILE" "$RESPONSE_FILE"

echo "=== FIRST REQUEST (Analyze TSLA) ==="
curl -s -X POST http://127.0.0.1:5001/chat \
     -b "$COOKIE_FILE" -c "$COOKIE_FILE" \
     -H "Content-Type: application/json" \
     -d '{"history": [{"role": "user", "content": "Analyze TSLA"}]}' | head -n 20

echo "\n=== SECOND REQUEST (Analyze GOOGL) ==="
curl -s -X POST http://127.0.0.1:5001/chat \
     -b "$COOKIE_FILE" -c "$COOKIE_FILE" \
     -H "Content-Type: application/json" \
     -d '{"history": [{"role": "user", "content": "Analyze GOOGL"}]}' > "$RESPONSE_FILE"

cat "$RESPONSE_FILE" | python3 -c "import sys, json; data = json.load(sys.stdin); print('Reply:', data.get('reply')); print('Tool Updates:', json.dumps(data.get('tool_updates', []), indent=2))"

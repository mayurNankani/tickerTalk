#!/usr/bin/env bash
# Quick test script for comparing recommendation systems

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VENV_PYTHON="$ROOT_DIR/.venv/bin/python"
COMPARE_SCRIPT="$ROOT_DIR/scripts/testing/compare_systems.py"

echo "Stock Recommendation System Comparison Tool"
echo ""

if [ $# -eq 0 ]; then
    echo "Usage: ./scripts/testing/test_comparison.sh TICKER1 [TICKER2 ...]"
    echo ""
    echo "Testing with AAPL as default..."
    echo ""
    "$VENV_PYTHON" "$COMPARE_SCRIPT" AAPL
else
    "$VENV_PYTHON" "$COMPARE_SCRIPT" "$@"
fi

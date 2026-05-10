#!/bin/bash
# Quick test script for comparing recommendation systems

VENV_PYTHON="/Users/mayurmnankani/stockMarketAgent/.venv/bin/python"

echo "🔍 Stock Recommendation System Comparison Tool"
echo ""

if [ $# -eq 0 ]; then
    echo "Usage: ./test_comparison.sh TICKER1 [TICKER2 ...]"
    echo ""
    echo "Examples:"
    echo "  ./test_comparison.sh AAPL"
    echo "  ./test_comparison.sh AAPL TSLA GOOGL"
    echo "  ./test_comparison.sh QQQ SPY"
    echo ""
    echo "Testing with AAPL as default..."
    echo ""
    $VENV_PYTHON compare_systems.py AAPL
else
    $VENV_PYTHON compare_systems.py "$@"
fi

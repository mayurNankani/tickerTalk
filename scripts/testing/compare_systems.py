#!/usr/bin/env python3
"""Compare old vs improved recommendation systems side-by-side.

Usage: python scripts/testing/compare_systems.py AAPL TSLA GOOGL
"""

import sys

from src.agent_improved import StockAnalysisAgentImproved


def print_separator(char="=", length=80):
    print(char * length)


def print_recommendation(rec, system_name):
    """Print a single recommendation in a formatted way."""
    print(f"\n{system_name}:")
    print("-" * 40)

    for timeframe in ["short_term", "medium_term", "long_term"]:
        if timeframe in rec:
            data = rec[timeframe]
            print(f"\n  {timeframe.replace('_', '-').title()}:")
            print(f"    Label:      {data.get('label', 'N/A')}")

            if "score" in data:
                print(f"    Score:      {data['score']}/100")

            if "confidence" in data:
                print(f"    Confidence: {data['confidence']}%")

            summary = data.get("summary", "N/A")
            if len(summary) > 60:
                summary = summary[:57] + "..."
            print(f"    Summary:    {summary}")


def compare_stock(ticker):
    """Compare both systems for a single stock."""
    print_separator("=")
    print(f"COMPARING RECOMMENDATIONS FOR: {ticker.upper()}")
    print_separator("=")

    print("\nFetching data and computing recommendations...")

    try:
        new_agent = StockAnalysisAgentImproved()
        new_rec = new_agent.get_recommendation(ticker)
    except Exception as exc:
        print(f"\nNEW SYSTEM ERROR: {exc}")
        new_rec = None

    if new_rec:
        print_recommendation(new_rec, "NEW SYSTEM (Weighted Continuous Scoring)")

    print("\n" + "=" * 80 + "\n")


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/testing/compare_systems.py TICKER1 [TICKER2 ...]")
        sys.exit(1)

    tickers = sys.argv[1:]
    print("\nSTOCK RECOMMENDATION REPORT")
    print("Showing weighted multi-horizon recommendations from the current engine\n")

    for i, ticker in enumerate(tickers):
        if i > 0:
            print("\n\n")
        compare_stock(ticker)

    print("\nComparison complete!")


if __name__ == "__main__":
    main()

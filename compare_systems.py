#!/usr/bin/env python3
"""
Compare old vs improved recommendation systems side-by-side.
Usage: python compare_systems.py AAPL TSLA GOOGL
"""

import sys
from src.agent import StockAnalysisAgent
from src.agent_improved import StockAnalysisAgentImproved

def print_separator(char="=", length=80):
    print(char * length)

def print_recommendation(rec, system_name):
    """Print a single recommendation in a formatted way"""
    print(f"\n{system_name}:")
    print("-" * 40)
    
    for timeframe in ["short_term", "medium_term", "long_term"]:
        if timeframe in rec:
            data = rec[timeframe]
            print(f"\n  {timeframe.replace('_', '-').title()}:")
            print(f"    Label:      {data.get('label', 'N/A')}")
            
            # Show score if available (new system)
            if 'score' in data:
                print(f"    Score:      {data['score']}/100")
            
            # Show confidence if available (new system)
            if 'confidence' in data:
                print(f"    Confidence: {data['confidence']}%")
            
            # Show summary
            summary = data.get('summary', 'N/A')
            if len(summary) > 60:
                summary = summary[:57] + "..."
            print(f"    Summary:    {summary}")

def compare_stock(ticker):
    """Compare both systems for a single stock"""
    print_separator("=")
    print(f"COMPARING RECOMMENDATIONS FOR: {ticker.upper()}")
    print_separator("=")
    
    # Get recommendations from both systems
    print("\nFetching data and computing recommendations...")
    
    try:
        old_agent = StockAnalysisAgent()
        old_rec = old_agent.get_recommendation(ticker)
    except Exception as e:
        print(f"\n❌ OLD SYSTEM ERROR: {e}")
        old_rec = None
    
    try:
        new_agent = StockAnalysisAgentImproved()
        new_rec = new_agent.get_recommendation(ticker)
    except Exception as e:
        print(f"\n❌ NEW SYSTEM ERROR: {e}")
        new_rec = None
    
    # Display results
    if old_rec:
        print_recommendation(old_rec, "📊 OLD SYSTEM (Simple +1/+2 Scoring)")
    
    if new_rec:
        print_recommendation(new_rec, "🚀 NEW SYSTEM (Weighted Continuous Scoring)")
    
    # Show comparison summary
    if old_rec and new_rec:
        print("\n" + "=" * 80)
        print("COMPARISON SUMMARY:")
        print("=" * 80)
        
        for timeframe in ["short_term", "medium_term", "long_term"]:
            old_label = old_rec.get(timeframe, {}).get('label', 'N/A')
            new_label = new_rec.get(timeframe, {}).get('label', 'N/A')
            new_score = new_rec.get(timeframe, {}).get('score', 'N/A')
            new_conf = new_rec.get(timeframe, {}).get('confidence', 'N/A')
            
            agreement = "✅ SAME" if old_label == new_label else "⚠️  DIFFERENT"
            
            print(f"\n{timeframe.replace('_', '-').title()}:")
            print(f"  Old: {old_label:12} | New: {new_label:12} (Score: {new_score}, Conf: {new_conf}%) {agreement}")
        
        # Show fundamental details comparison
        print("\n" + "-" * 80)
        print("FUNDAMENTAL ANALYSIS DETAILS:")
        print("-" * 80)
        
        old_fund = old_rec.get('fundamental', {})
        new_fund = new_rec.get('fundamental', {})
        
        print(f"\nOld System:")
        print(f"  Label:   {old_fund.get('label', 'N/A')}")
        print(f"  Summary: {old_fund.get('summary', 'N/A')[:70]}...")
        
        print(f"\nNew System:")
        print(f"  Label:      {new_fund.get('label', 'N/A')}")
        print(f"  Score:      {new_fund.get('score', 'N/A')}/100")
        print(f"  Confidence: {new_fund.get('confidence', 'N/A')}%")
        print(f"  Summary:    {new_fund.get('summary', 'N/A')[:70]}...")
        
        # Show technical details comparison
        print("\n" + "-" * 80)
        print("TECHNICAL ANALYSIS DETAILS:")
        print("-" * 80)
        
        old_tech = old_rec.get('technical', {})
        new_tech = new_rec.get('technical', {})
        
        print(f"\nOld System:")
        print(f"  Label:   {old_tech.get('label', 'N/A')}")
        print(f"  Summary: {old_tech.get('summary', 'N/A')[:70]}...")
        
        print(f"\nNew System:")
        print(f"  Label:      {new_tech.get('label', 'N/A')}")
        print(f"  Score:      {new_tech.get('score', 'N/A')}/100")
        print(f"  Confidence: {new_tech.get('confidence', 'N/A')}%")
        print(f"  Summary:    {new_tech.get('summary', 'N/A')[:70]}...")
    
    print("\n" + "=" * 80 + "\n")

def main():
    if len(sys.argv) < 2:
        print("Usage: python compare_systems.py TICKER1 [TICKER2 ...]")
        print("\nExamples:")
        print("  python compare_systems.py AAPL")
        print("  python compare_systems.py AAPL TSLA GOOGL MSFT")
        print("  python compare_systems.py QQQ SPY")
        sys.exit(1)
    
    tickers = sys.argv[1:]
    
    print("\n🔍 STOCK RECOMMENDATION SYSTEM COMPARISON")
    print("Comparing OLD (simple) vs NEW (weighted) scoring systems\n")
    
    for i, ticker in enumerate(tickers):
        if i > 0:
            print("\n" * 2)  # Space between stocks
        
        compare_stock(ticker)
    
    print("\n✅ Comparison complete!")
    print("\nKey differences to look for:")
    print("  • NEW system provides numerical scores (0-100) for more granularity")
    print("  • NEW system includes confidence percentages")
    print("  • NEW system uses weighted metrics (PEG > PE, Earnings Growth > Revenue Growth)")
    print("  • NEW system has smooth scoring curves instead of binary thresholds")
    print("  • Labels may differ when stocks are near threshold boundaries")
    print()

if __name__ == "__main__":
    main()

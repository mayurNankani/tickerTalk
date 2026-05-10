import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.tools.company_search import CompanySearch
from src.mcp_agent import YahooFinanceAgent
from src.agent import StockAnalysisAgent

def smart_orchestrator():
    company_search = CompanySearch()
    yahoo_agent = YahooFinanceAgent()
    analysis_agent = StockAnalysisAgent()

    while True:
        company_name = input("\nEnter a company name (or type 'exit' to quit): ").strip()
        if company_name.lower() in ['exit', 'quit']:
            print("\nThanks for using the Stock Market MCP Orchestrator! Goodbye! 👋")
            break
        search_results = company_search.analyze(company_name)
        matches = search_results.get("matches", [])
        if not matches:
            print("❌ No matching companies found. Please try a different name.")
            continue

        print("\n📝 Found these matching companies:")
        for i, match in enumerate(matches, 1):
            print(f"{i}. {match['long_name'] or match['short_name']} ({match['symbol']}) - {match['exchange']}")

        if len(matches) > 1:
            while True:
                choice = input("\nPlease enter the number of the company you're interested in: ")
                try:
                    choice_idx = int(choice) - 1
                    if 0 <= choice_idx < len(matches):
                        ticker = matches[choice_idx]['symbol']
                        company_name = matches[choice_idx]['long_name'] or matches[choice_idx]['short_name']
                        break
                    else:
                        print("❌ Invalid number. Please try again.")
                except ValueError:
                    print("❌ Please enter a valid number.")
        else:
            ticker = matches[0]['symbol']
            company_name = matches[0]['long_name'] or matches[0]['short_name']

        # Query YahooFinanceAgent only (remove NewsAgent)
        quote_result = yahoo_agent.handle({"action": "get_quote", "parameters": {"ticker": ticker}})
        analysis = analysis_agent.analyze_stock(ticker)
        recommendations = analysis_agent.get_recommendation(ticker)

        print(f"\n=== {company_name} ({ticker}) ===")
        if quote_result["status"] == "ok":
            data = quote_result["data"]
            print(f"Price: {data.get('price')} {data.get('currency')} | Name: {data.get('name')}")
        else:
            print(f"Quote error: {quote_result['error']}")

        # Show multi-horizon recommendations
        short = recommendations.get('short_term', {})
        medium = recommendations.get('medium_term', {})
        long = recommendations.get('long_term', {})
        print("\n🕒 Time Horizon Recommendations:")
        print(f"  • Short-term (1 week): {short.get('label', 'N/A')}")
        if short.get('summary'):
            print(f"    - {short['summary']}")
        print(f"  • Medium-term (3 months): {medium.get('label', 'N/A')}")
        if medium.get('summary'):
            print(f"    - {medium['summary']}")
        print(f"  • Long-term (6-12 months): {long.get('label', 'N/A')}")
        if long.get('summary'):
            print(f"    - {long['summary']}")

if __name__ == "__main__":
    smart_orchestrator()

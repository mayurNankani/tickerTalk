from src.agent_improved import StockAnalysisAgentImproved as StockAnalysisAgent
from src.agent_improved import FUNDAMENTAL_TOOLTIPS, TECHNICAL_TOOLTIPS

def print_welcome():
    print("\n=== Stock Market Analysis Chatbot ===")
    print("I can help you analyze stocks and get market insights.")
    print("Type 'quit' or 'exit' to end the conversation.")
    print("=====================================\n")

def format_analysis_results(analysis):
    """Format the analysis results in a readable way"""
    fundamental = analysis["fundamental_analysis"]
    technical = analysis["technical_analysis"]
    fundamental_summary = analysis.get("fundamental_summary", [])
    technical_summary = analysis.get("technical_summary", [])
    
    output = []
    
    # Fundamental summary (no explanations)
    if fundamental_summary:
        output.append("\n📊 Fundamental Summary:")
        for line in fundamental_summary:
            metric = line.split(':')[0]
            value = line.split(':')[1].split('—')[0].strip() if '—' in line else line.split(':')[1].strip()
            output.append(f"  • {metric}: {value}")
    else:
        output.append("\n📊 Fundamental Analysis:")
        for key, value in fundamental.items():
            if value is not None:
                formatted_key = key.replace('_', ' ').title()
                output.append(f"  • {formatted_key}: {value}")
    
    # Technical summary (no explanations)
    if technical_summary:
        output.append("\n📈 Technical Summary:")
        for line in technical_summary:
            metric = line.split(':')[0]
            value = line.split(':')[1].split('—')[0].strip() if '—' in line else line.split(':')[1].strip()
            output.append(f"  • {metric}: {value}")
    else:
        output.append("\n📈 Technical Analysis:")
        for key, value in technical.items():
            if value is not None:
                formatted_key = key.replace('_', ' ').title()
                if isinstance(value, float):
                    value = round(value, 2)
                output.append(f"  • {formatted_key}: {value}")
    
    return "\n".join(output)

def chatbot():
    agent = StockAnalysisAgent()
    print_welcome()
    
    while True:
        # Get user input
        company = input("\n🤖 Please enter a company name to analyze (or type a metric for info, or 'quit' to exit): ").strip()

        if company.lower() in ['quit', 'exit']:
            print("\nThanks for using the Stock Market Analysis Chatbot! Goodbye! 👋")
            break

        # Check if input is a metric name
        if company in FUNDAMENTAL_TOOLTIPS:
            print(f"\nℹ️ {company}: {FUNDAMENTAL_TOOLTIPS[company]}")
            continue
        if company in TECHNICAL_TOOLTIPS:
            print(f"\nℹ️ {company}: {TECHNICAL_TOOLTIPS[company]}")
            continue

        print(f"\n🔍 Searching for: {company}")
        
        # Search for the company
        search_results = agent.find_ticker(company)
        
        if search_results.get("error"):
            print(f"❌ Error: {search_results['error']}")
            continue
        
        matches = search_results.get("matches", [])
        if not matches:
            print("❌ No matching companies found. Please try a different name.")
            continue
        
        # Show matches
        print("\n📝 Found these matching companies:")
        for i, match in enumerate(matches, 1):
            print(f"{i}. {match['long_name']} ({match['symbol']}) - {match['exchange']}")
        
        # If multiple matches, let user choose
        if len(matches) > 1:
            while True:
                choice = input("\nPlease enter the number of the company you're interested in: ")
                try:
                    choice_idx = int(choice) - 1
                    if 0 <= choice_idx < len(matches):
                        ticker = matches[choice_idx]['symbol']
                        break
                    else:
                        print("❌ Invalid number. Please try again.")
                except ValueError:
                    print("❌ Please enter a valid number.")
        else:
            ticker = matches[0]['symbol']
        
        # Get and show analysis
        print(f"\n⏳ Analyzing {ticker}...")
        analysis = agent.analyze_stock(ticker)
        print(format_analysis_results(analysis))
        # Show news articles if available
        news = analysis.get('fundamental_analysis', {}).get('news', [])
        if news and any(item.get('headline') for item in news):
            print("\n📰 Recent News Headlines:")
            for i, item in enumerate(news, 1):
                headline = item.get('headline', '')
                if not headline:
                    continue
                summary = item.get('summary', '')
                url = item.get('url', '')
                print(f"  {i}. {headline}")
                if summary:
                    print(f"     - {summary}")
                if url:
                    print(f"     Link: {url}")
        
        # Get and show recommendations
        recommendations = agent.get_recommendation(ticker)

        print("\n💡 Investment Recommendations:")
        f_rec = recommendations.get('fundamental', {})
        t_rec = recommendations.get('technical', {})
        final = recommendations.get('final', {})

        # Fundamental
        f_label = f_rec.get('label') if isinstance(f_rec, dict) else f_rec
        f_summary = f_rec.get('summary', '') if isinstance(f_rec, dict) else ''
        print(f"  • Fundamental Analysis: {f_label}")
        if f_summary:
            print(f"    - {f_summary}")

        # Technical
        t_label = t_rec.get('label') if isinstance(t_rec, dict) else t_rec
        t_summary = t_rec.get('summary', '') if isinstance(t_rec, dict) else ''
        print(f"  • Technical Analysis: {t_label}")
        if t_summary:
            print(f"    - {t_summary}")

        # Current price (show before final recommendation)
        current_price = analysis.get('technical_analysis', {}).get('current_price')
        if current_price is not None:
            try:
                price_display = round(float(current_price), 2)
            except Exception:
                price_display = current_price
            print(f"\n💲 Current price: {price_display}")

        # Remove final recommendation output (now handled by time horizon recommendations)
        
        # Show multi-horizon recommendations with explanations in summary only
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

        print("\n💡 If you want more information about any metric, type its name (e.g., 'pe_ratio') or ask a question about it.")
        print("\n-------------------------------------------")

if __name__ == "__main__":
    chatbot()
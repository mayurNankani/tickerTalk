from flask import Flask, request, jsonify, render_template_string
import sys
import os
import re
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.tools.company_search import CompanySearch
from src.mcp_agent import YahooFinanceAgent
from src.agent import StockAnalysisAgent
from src.tools.rss_news import RSSNewsAgent

# --- Tooltip dictionaries and helpers ---
FUNDAMENTAL_TOOLTIPS = {
    "market_cap": "Company size measured as share price × shares outstanding; context for stability/risk.",
    "pe_ratio": "Price divided by last 12 months' earnings; lower often means cheaper relative to earnings.",
    "forward_pe": "Price divided by projected earnings; shows valuation based on expected profit.",
    "peg_ratio": "PE divided by earnings growth rate; adjusts valuation for growth (≈1 ≈ fair).",
    "price_to_book": "Price relative to book value per share; useful for asset-heavy businesses.",
    "revenue_growth": "Year-over-year top-line growth; indicates demand and expansion speed.",
    "earnings_growth": "Growth in net income; shows profit trend and scalability.",
    "profit_margins": "Net profit ÷ revenue; higher = more profit retained per sale.",
    "return_on_equity": "Net income ÷ shareholder equity; how well equity generates profit.",
    "debt_to_equity": "Total debt ÷ shareholders' equity; higher means more leverage risk.",
    "current_ratio": "Current assets ÷ current liabilities; measures short-term liquidity.",
    "dividend_yield": "Annual dividends ÷ share price; income return from holding the stock."
}
TECHNICAL_TOOLTIPS = {
    "current_price": "The most recent closing price; immediate market value reference.",
    "price_change": "Percent change from previous close; shows short-term movement.",
    "rsi": "Relative Strength Index (0–100); <30 often oversold (buy), >70 overbought (sell).",
    "macd": "MACD line (short EMA − long EMA); shows trend direction and momentum.",
    "macd_signal": "Smoothed MACD used for crossovers (trade signal line).",
    "macd_hist": "MACD − signal; rising positive histogram shows strengthening bullish momentum.",
    "adx": "Average Directional Index; measures trend strength (values > ~25 indicate a strong trend).",
    "bb_width": "Width of Bollinger Bands relative to MA; narrow = low volatility, wide = high volatility.",
    "atr": "Average True Range; average size of daily price moves (volatility measure).",
    "mfi": "Money Flow Index; volume-weighted momentum oscillator, extremes suggest overbought/oversold.",
    "sma_20": "20-period Simple Moving Average; price above suggests short-term uptrend.",
    "sma_50": "50-period Simple Moving Average; price above suggests medium-term uptrend.",
    "sma_20_cross_50": "True when SMA20 crosses above SMA50 indicating a bullish trend change (golden cross)."
}
def add_tooltips(text):
    all_keys = list(FUNDAMENTAL_TOOLTIPS.keys()) + list(TECHNICAL_TOOLTIPS.keys())
    all_keys.sort(key=len, reverse=True)
    for key in all_keys:
        tooltip = FUNDAMENTAL_TOOLTIPS.get(key) or TECHNICAL_TOOLTIPS.get(key)
        text = re.sub(rf'\b{re.escape(key)}\b', f'<span title="{tooltip}">{key}</span>', text, flags=re.IGNORECASE)
    return text
def to_bullets(text):
    items = [item.strip() for item in text.split(',') if item.strip()]
    if not items or (len(items) == 1 and not items[0]):
        return ''
    return '<ul style="margin: 0 0 8px 18px; padding: 0;">' + ''.join(f'<li>{item}</li>' for item in items) + '</ul>'
def expand_block(term, label, bar, bullets, idx):
    return f'''
<div style="margin-bottom:18px;">
  <b>{term}: {label}</b><br>
  {bar}
  <a href="#" onclick="var e=document.getElementById('reasons_{idx}');if(e.style.display==='none'){{e.style.display='block';this.innerText='Hide reasons';}}else{{e.style.display='none';this.innerText='Show reasons';}}return false;" style="font-size:0.95em;">Show reasons</a>
  <div id="reasons_{idx}" style="display:none;">{bullets}</div>
</div>
'''

def heatmap(label):
    """Return an HTML bar colored by recommendation label."""
    color = {
        'STRONG BUY': '#27ae60',
        'BUY': '#2ecc71',
        'HOLD': '#f1c40f',
        'SELL': '#e74c3c',
    }.get(label.upper(), '#bdc3c7')
    # If label is STRONG BUY, bold 'STRONG' and color the whole bar green
    if label.upper() == 'STRONG BUY':
        label_html = '<b>STRONG</b> BUY'
    else:
        label_html = label
    return f'<div style="display:inline-block;width:130px;height:16px;background:{color};border-radius:6px;text-align:center;color:#fff;font-weight:bold;line-height:16px;font-size:0.95em;">{label_html}</div>'

def format_quote_html(quote_result):
    if not quote_result or quote_result.get('status') != 'ok':
        return ''
    data = quote_result.get('data', {})
    price = data.get('price', 'N/A')
    currency = data.get('currency', '')
    name = data.get('name', '')
    return f'<b>Price:</b> {price} {currency} <b>Name:</b> {name}'

app = Flask(__name__, static_folder='.', static_url_path='')

company_search = CompanySearch()
yahoo_agent = YahooFinanceAgent()
analysis_agent = StockAnalysisAgent()
rss_news_agent = RSSNewsAgent()

@app.route('/')
def index():
    with open(os.path.join(os.path.dirname(__file__), 'index.html')) as f:
        return f.read()

@app.route('/analyze', methods=['POST'])
def analyze():
    data = request.get_json()
    company_name = data.get('company', '').strip()
    if not company_name:
        return jsonify({'error': 'Please enter a company name.'})
    search_results = company_search.analyze(company_name)
    matches = search_results.get('matches', [])
    if not matches:
        return jsonify({'error': 'No matching companies found.'})

    match = matches[0]
    ticker = match['symbol']
    company_name = match['long_name'] or match['short_name']
    quote_result = yahoo_agent.handle({"action": "get_quote", "parameters": {"ticker": ticker}})
    recommendations = analysis_agent.get_recommendation(ticker)
    short = recommendations.get('short_term', {})
    medium = recommendations.get('medium_term', {})
    long = recommendations.get('long_term', {})
    # For medium and long, show the full rationale, not just summary
    medium_label = medium.get('label', 'N/A')
    medium_summary = medium.get('summary', '')
    long_label = long.get('label', 'N/A')
    long_summary = long.get('summary', '')

    # Get news headlines for the ticker
    news_result = rss_news_agent.analyze(ticker)
    news_html = ''
    if news_result.get('news'):
        news_html = '<br><b>Recent News:</b><ul style="margin:8px 0 8px 18px;">' + ''.join(
            f'<li><a href="{item["url"]}" target="_blank">{item["headline"]}</a></li>' for item in news_result['news'] if item.get('headline')
        ) + '</ul>'

    quote_html = format_quote_html(quote_result)
    result = (
        f"<b>{company_name} ({ticker})</b><br>"
        f"{quote_html}<br>"
        f"{news_html}"
        f"<br><b>Time Horizon Recommendations:</b><br>"
        f"<br>"
        f"{expand_block('Short-term (1 week)', short.get('label', 'N/A'), heatmap(short.get('label', 'N/A')), to_bullets(add_tooltips(short.get('summary',''))), 1)}"
        f"{expand_block('Medium-term (3 months)', medium_label, heatmap(medium_label), to_bullets(add_tooltips(medium_summary)), 2)}"
        f"{expand_block('Long-term (6-12 months)', long_label, heatmap(long_label), to_bullets(add_tooltips(long_summary)), 3)}"
    )
    return jsonify({'result': result})

if __name__ == '__main__':
    app.run(debug=True)

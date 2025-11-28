from flask import Flask, request, jsonify, render_template_string, session
import sys
import os
import re
import requests
import json
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.tools.company_search import CompanySearch
from src.mcp_agent import YahooFinanceAgent
from src.agent import StockAnalysisAgent
from src.tools.rss_news import RSSNewsAgent

# For fetching full article text
from src.tools.article_scraper import fetch_article_text

# For web search fallback
from src.tools.web_search import ddg_search


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
    return f'<b>Price:</b> {price} {currency}'

app = Flask(__name__, static_folder='.', static_url_path='')
# Set a secret key for session support
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'replace-this-with-a-random-secret')

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
    # Compose recommendations block and rewrite only that with LLM
    recommendations_html = (
        f"<b>Time Horizon Recommendations:</b><br><br>"
        f"{expand_block('Short-term (1 week)', short.get('label', 'N/A'), heatmap(short.get('label', 'N/A')), to_bullets(add_tooltips(short.get('summary',''))), 1)}"
        f"{expand_block('Medium-term (3 months)', medium_label, heatmap(medium_label), to_bullets(add_tooltips(medium_summary)), 2)}"
        f"{expand_block('Long-term (6-12 months)', long_label, heatmap(long_label), to_bullets(add_tooltips(long_summary)), 3)}"
    )
    recommendations_human = make_human(recommendations_html)
    result = (
        f"<b>{company_name} ({ticker})</b><br><br>"
        f"{quote_html}<br><br>"
        f"{news_html}<br><br>"
        f"{recommendations_human}"
    )
    return jsonify({'result': result})

@app.route('/chat', methods=['POST'])
def chat():
    global yahoo_agent
    data = request.get_json()
    history = data.get('history', [])
    user_message = history[-1]['content'] if history else ''

    # Detect if user is asking about earnings
    if 'earnings' in user_message.lower() or 'earnings report' in user_message.lower():
        import re as _re
        ticker = None
        context = session.get('analysis_context', '')
        m = _re.search(r'\(([^)]+)\)', context)
        if m:
            ticker = m.group(1)
        if not ticker and history:
            for h in reversed(history):
                t = h.get('content','')
                m2 = _re.search(r'\(([^)]+)\)', t)
                if m2:
                    ticker = m2.group(1)
                    break
        if ticker:
            earnings_result = yahoo_agent.handle({"action": "get_earnings", "parameters": {"ticker": ticker}})
            if earnings_result.get('status') == 'ok':
                data = earnings_result['data']
                next_earnings = data.get('next_earnings')
                earnings_history = data.get('earnings_history', [])
                html = f"<b>Earnings for {ticker}:</b><br>"
                if next_earnings:
                    html += "<b>Next Earnings Event:</b><ul>"
                    for k, v in next_earnings.items():
                        html += f"<li><b>{k}:</b> {v}</li>"
                    html += "</ul>"
                if earnings_history:
                    # Always show date as first column, even if named differently
                    date_keys = ['Earnings Date', 'index', 'date']
                    columns = list(earnings_history[0].keys())
                    date_col = next((k for k in date_keys if k in columns), columns[0])
                    # Move date_col to front
                    columns = [date_col] + [c for c in columns if c != date_col]
                    html += "<b>Recent Earnings History:</b><table border='1' cellpadding='4' style='border-collapse:collapse;margin-top:6px;'><tr>"
                    for col in columns:
                        html += f"<th>{col}</th>"
                    html += "</tr>"
                    for e in earnings_history[:5]:
                        html += "<tr>"
                        for col in columns:
                            html += f"<td>{e.get(col, '')}</td>"
                        html += "</tr>"
                    html += "</table>"
                if not next_earnings and not earnings_history:
                    html += "No earnings data found."
                return jsonify({'reply': html})
            else:
                return jsonify({'reply': f"Could not fetch earnings for {ticker}."})
        else:
            return jsonify({'reply': "Could not determine ticker for earnings lookup. Please specify the stock symbol."})

    llm_provider = os.getenv('LLM_PROVIDER', 'gemini').lower()
    if 'analysis_context' not in session:
        session['analysis_context'] = ''
    news_articles = session.get('last_news_articles', [])
    matched_article = None
    import re
    idx_match = re.search(r'(first|second|third|fourth|fifth|[0-9]+)[^\w]*(news|article|headline)', user_message, re.IGNORECASE)
    idx_map = {'first': 0, 'second': 1, 'third': 2, 'fourth': 3, 'fifth': 4}
    if idx_match and news_articles:
        idx_str = idx_match.group(1).lower()
        idx = idx_map.get(idx_str)
        if idx is None:
            try:
                idx = int(idx_str) - 1
            except Exception:
                idx = None
        if idx is not None and 0 <= idx < len(news_articles):
            matched_article = news_articles[idx]
    if not matched_article and news_articles:
        for article in news_articles:
            if article.get('headline') and article['headline'].lower() in user_message.lower():
                matched_article = article
                break

    # Fallback: If not a news or stock context, try web search
    # Only trigger if not initial stock analysis and not matched_article
    if len(history) > 1 and not matched_article and not session.get('analysis_context', '').strip():
        search_results = ddg_search(user_message)
        if search_results:
            reply = '<b>Web Search Results:</b><ul>'
            for r in search_results:
                reply += f'<li><a href="{r["url"]}" target="_blank">{r["title"]}</a><br><span style="font-size:0.95em;">{r["snippet"]}</span></li>'
            reply += '</ul>'
        else:
            reply = "Sorry, I couldn't find anything relevant on the web."
        return jsonify({'reply': reply})

    llm_provider = os.getenv('LLM_PROVIDER', 'gemini').lower()

    # Use Flask session to store analysis context per user
    if 'analysis_context' not in session:
        session['analysis_context'] = ''

    # If this is the first message or context is empty, treat as stock query and run analysis
    if len(history) == 1 or not session['analysis_context']:
        company_name = history[0]['content'].strip()
        # Run analyze logic
        company_search = CompanySearch()
        yahoo_agent = YahooFinanceAgent()
        analysis_agent = StockAnalysisAgent()
        rss_news_agent = RSSNewsAgent()
        search_results = company_search.analyze(company_name)
        matches = search_results.get('matches', [])
        if not matches:
            return jsonify({'reply': f"No matching companies found for '{company_name}'."})
        match = matches[0]
        ticker = match['symbol']
        company_name = match['long_name'] or match['short_name']
        quote_result = yahoo_agent.handle({"action": "get_quote", "parameters": {"ticker": ticker}})
        recommendations = analysis_agent.get_recommendation(ticker)
        short = recommendations.get('short_term', {})
        medium = recommendations.get('medium_term', {})
        long = recommendations.get('long_term', {})
        medium_label = medium.get('label', 'N/A')
        medium_summary = medium.get('summary', '')
        long_label = long.get('label', 'N/A')
        long_summary = long.get('summary', '')
        news_result = rss_news_agent.analyze(ticker)
        news_html = ''
        if news_result.get('news'):
            news_html = '<br><b>Recent News:</b><ul style="margin:8px 0 8px 18px;">' + ''.join(
                f'<li><a href="{item["url"]}" target="_blank">{item["headline"]}</a></li>' for item in news_result['news'] if item.get('headline')
            ) + '</ul>'

        quote_html = format_quote_html(quote_result)
        recommendations_html = (
            f"<b>Time Horizon Recommendations:</b><br><br>"
            f"{expand_block('Short-term (1 week)', short.get('label', 'N/A'), heatmap(short.get('label', 'N/A')), to_bullets(add_tooltips(short.get('summary',''))), 1)}"
            f"{expand_block('Medium-term (3 months)', medium_label, heatmap(medium_label), to_bullets(add_tooltips(medium_summary)), 2)}"
            f"{expand_block('Long-term (6-12 months)', long_label, heatmap(long_label), to_bullets(add_tooltips(long_summary)), 3)}"
        )
        recommendations_human = recommendations_html
        result = (
            f"<b>{company_name} ({ticker})</b><br>"
            f"{quote_html}<br>"
            f"{news_html}<br><br>"
            f"{recommendations_human}"
        )
        session['analysis_context'] = result
        # Store news articles in session for follow-up summarization
        session['last_news_articles'] = news_result.get('news', [])
        return jsonify({'reply': result})

    # For follow-up messages, check if user is asking about a news article
    user_message = history[-1]['content'] if history else ''
    news_articles = session.get('last_news_articles', [])
    # Try to match by headline or index (e.g., "Tell me more about the first news" or by headline text)
    matched_article = None
    import re
    idx_match = re.search(r'(first|second|third|fourth|fifth|[0-9]+)[^\w]*(news|article|headline)', user_message, re.IGNORECASE)
    idx_map = {'first': 0, 'second': 1, 'third': 2, 'fourth': 3, 'fifth': 4}
    if idx_match and news_articles:
        idx_str = idx_match.group(1).lower()
        idx = idx_map.get(idx_str)
        if idx is None:
            try:
                idx = int(idx_str) - 1
            except Exception:
                idx = None
        if idx is not None and 0 <= idx < len(news_articles):
            matched_article = news_articles[idx]
    # Check for headline match
    if not matched_article and news_articles:
        for article in news_articles:
            if article.get('headline') and article['headline'].lower() in user_message.lower():
                matched_article = article
                break
    if matched_article:
        # Fetch full article content
        article_url = matched_article.get('url', '')
        article_content = fetch_article_text(article_url) if article_url else ''
        # Summarize the article using the LLM
        article_text = (
            f"Headline: {matched_article.get('headline','')}\n"
            f"URL: {article_url}\n"
            f"Summary: {matched_article.get('summary','')}\n"
            f"Content: {article_content}"
        )
        llm_provider = os.getenv('LLM_PROVIDER', 'gemini').lower()
        if llm_provider == 'ollama':
            # Use Ollama with selectable model
            import time
            context = session['analysis_context']
            # Map dropdown value to actual Ollama model name
            model_map = {
                'llama3': 'llama3:8b',
                'qwen3': 'qwen3:4b',
                'gemma3': 'gemma3:4b',
            }
            model_key = request.json.get('model', 'llama3')
            model = model_map.get(model_key, 'llama3')
            prompt = (
                f"Here is a news article about a stock. Please summarize it in 2-3 sentences for a general audience.\n{article_text}\n"
                f"If you don't have enough information, say so."
            )
            try:
                start_time = time.time()
                r = requests.post(
                    'http://localhost:11434/api/chat',
                    json={
                        'model': model,
                        'messages': [
                            {'role': 'user', 'content': prompt}
                        ],
                        'stream': False
                    },
                    timeout=60
                )
                elapsed = time.time() - start_time
                print(f"[Ollama] Model '{model}' response time: {elapsed:.2f} seconds")
                r.raise_for_status()
                reply = r.json()['message']['content']
            except Exception as e:
                reply = f"Sorry, {model} (Ollama) could not process your request. ({e})"
            return jsonify({'reply': reply})
        else:
            # Default: Gemini
            GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
            if not GEMINI_API_KEY:
                return jsonify({'reply': "Gemini API key not set. Please set GEMINI_API_KEY in your environment."})
            gemini_history = []
            gemini_history.append({'role': 'user', 'parts': [{'text': f"Here is a news article about a stock. Please summarize it in 2-3 sentences for a general audience.\n{article_text}\nIf you don't have enough information, say so."}]})
            try:
                r = requests.post(
                    'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent',
                    headers={
                        'Content-Type': 'application/json'
                    },
                    params={
                        'key': GEMINI_API_KEY
                    },
                    json={
                        'contents': gemini_history
                    },
                    timeout=15
                )
                r.raise_for_status()
                reply = r.json()['candidates'][0]['content']['parts'][0]['text']
                if reply.strip().startswith('```') or 'tool_code' in reply or 'get_stock_info' in reply:
                    reply = "I don't know. Please ask about information shown above or request a different stock."
            except Exception as e:
                reply = f"Sorry, Gemini could not process your request. ({e})"
            return jsonify({'reply': reply})
    # For all other follow-ups, use selected LLM
    if llm_provider == 'ollama':
        # Use Ollama with selectable model
        import time
        context = session['analysis_context']
        user_message = history[-1]['content'] if history else ''
        # Map dropdown value to actual Ollama model name
        model_map = {
            'llama3': 'llama3:8b',
            'qwen3': 'qwen3:4b',
            'gemma3': 'gemma3:4b',  # adjust to your actual Ollama model name
        }
        model_key = request.json.get('model', 'llama3')
        model = model_map.get(model_key, 'llama3')
        prompt = (
            f"Here is the stock analysis context for reference (from yfinance and internal agents):\n{context}\n\n"
            f"Now answer the user's question: {user_message}"
        )
        try:
            start_time = time.time()
            r = requests.post(
                'http://localhost:11434/api/chat',
                json={
                    'model': model,
                    'messages': [
                        {'role': 'user', 'content': prompt}
                    ],
                    'stream': False
                },
                timeout=60
            )
            elapsed = time.time() - start_time
            print(f"[Ollama] Model '{model}' response time: {elapsed:.2f} seconds")
            r.raise_for_status()
            reply = r.json()['message']['content']
        except Exception as e:
            reply = f"Sorry, {model} (Ollama) could not process your request. ({e})"
        return jsonify({'reply': reply})
    else:
        # Default: Gemini
                    # Do NOT call the language model for the initial response
        GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
        if not GEMINI_API_KEY:
            return jsonify({'reply': "Gemini API key not set. Please set GEMINI_API_KEY in your environment."})
        gemini_history = []
        gemini_history.append({'role': 'user', 'parts': [{'text': f"Here is the stock analysis context for reference (from yfinance and internal agents):\n{session['analysis_context']}"}]})
        if history:
            gemini_history.append({'role': 'user', 'parts': [{'text': history[-1]['content']}]})
        try:
            r = requests.post(
                'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent',
                headers={
                    'Content-Type': 'application/json'
                },
                params={
                    'key': GEMINI_API_KEY
                },
                json={
                    'contents': gemini_history
                },
                timeout=15
            )
            r.raise_for_status()
            reply = r.json()['candidates'][0]['content']['parts'][0]['text']
            if reply.strip().startswith('```') or 'tool_code' in reply or 'get_stock_info' in reply:
                reply = "I don't know. Please ask about information shown above or request a different stock."
        except Exception as e:
            reply = f"Sorry, Gemini could not process your request. ({e})"
        return jsonify({'reply': reply})


# Helper to call LLM (Gemini or Ollama Llama3)
def make_human(response_html):
    llm_provider = os.getenv('LLM_PROVIDER', 'gemini').lower()
    model = request.json.get('model', 'llama3') if request and request.is_json else 'llama3'
    if llm_provider == 'ollama':
        # Use Ollama with selected model
        prompt = (
            "You are a helpful stock market assistant. Only use the information provided below, which comes from yfinance and internal agents. "
            "If you do not know the answer from the provided information, reply: 'I don't know.' "
            "Do not use any outside knowledge or make up answers. "
            "Rewrite the following stock analysis recommendations to sound more human, conversational, and friendly, but keep ALL the HTML tags and formatting EXACTLY as in the input. Do NOT remove, escape, or alter any HTML tags.\n\n"
            f"{response_html}"
        )
        try:
            r = requests.post(
                'http://localhost:11434/api/chat',
                json={
                    'model': model,
                    'messages': [
                        {'role': 'user', 'content': prompt}
                    ],
                    'stream': False
                },
                timeout=60
            )
            r.raise_for_status()
            reply = r.json()['message']['content']
            return reply
        except Exception:
            return response_html
    else:
        # Default: Gemini
        GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
        if not GEMINI_API_KEY:
            return response_html  # fallback if no key
        prompt = (
            "You are a helpful stock market assistant. Only use the information provided below, which comes from yfinance and internal agents. "
            "If you do not know the answer from the provided information, reply: 'I don't know.' "
            "Do not use any outside knowledge or make up answers. "
            "Rewrite the following stock analysis recommendations to sound more human, conversational, and friendly, but keep ALL the HTML tags and formatting EXACTLY as in the input. Do NOT remove, escape, or alter any HTML tags.\n\n"
            f"{response_html}"
        )
        try:
            r = requests.post(
                'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent',
                headers={
                    'Content-Type': 'application/json'
                },
                params={
                    'key': GEMINI_API_KEY
                },
                json={
                    'contents': [
                        {'role': 'user', 'parts': [{'text': prompt}]}
                    ]
                },
                timeout=15
            )
            r.raise_for_status()
            reply = r.json()['candidates'][0]['content']['parts'][0]['text']
            # Filter out code/tool responses
            if reply.strip().startswith('```') or 'tool_code' in reply or 'get_stock_info' in reply:
                return "I don't know. Please ask about information shown above or request a different stock."
            return reply
        except Exception:
            return response_html

if __name__ == '__main__':
    app.run(debug=True)

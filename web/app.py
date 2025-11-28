"""
Modern Stock Market Analysis Web Application
Flask backend with clean architecture and improved code organization
"""

import os
import sys
import re
import json
import time
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass

import requests
from flask import Flask, request, jsonify, session

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.tools.company_search import CompanySearch
from src.tools.rss_news import RSSNewsAgent
from src.tools.article_scraper import fetch_article_text
from src.tools.web_search import ddg_search
from src.mcp_agent import YahooFinanceAgent
from src.agent import StockAnalysisAgent


# ============================================================================
# Configuration
# ============================================================================

class Config:
    """Application configuration"""
    SECRET_KEY = os.getenv('FLASK_SECRET_KEY', 'replace-with-random-secret-key')
    LLM_PROVIDER = os.getenv('LLM_PROVIDER', 'gemini').lower()
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
    OLLAMA_URL = 'http://localhost:11434/api/chat'
    GEMINI_URL = 'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent'
    
    MODEL_MAP = {
        'llama3': 'llama3:8b',
        'qwen3': 'qwen3:4b',
        'gemma3': 'gemma3:4b',
    }


# ============================================================================
# Tooltip Data
# ============================================================================

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


# ============================================================================
# HTML Formatting Utilities
# ============================================================================

class HTMLFormatter:
    """Utilities for formatting analysis data as HTML"""
    
    @staticmethod
    def add_tooltips(text: str) -> str:
        """Add tooltip spans to technical terms"""
        all_keys = list(FUNDAMENTAL_TOOLTIPS.keys()) + list(TECHNICAL_TOOLTIPS.keys())
        all_keys.sort(key=len, reverse=True)
        
        for key in all_keys:
            tooltip = FUNDAMENTAL_TOOLTIPS.get(key) or TECHNICAL_TOOLTIPS.get(key)
            text = re.sub(
                rf'\b{re.escape(key)}\b',
                f'<span title="{tooltip}">{key}</span>',
                text,
                flags=re.IGNORECASE
            )
        return text
    
    @staticmethod
    def to_bullets(text: str) -> str:
        """Convert comma-separated text to HTML bullet list"""
        items = [item.strip() for item in text.split(',') if item.strip()]
        if not items:
            return ''
        
        bullets = ''.join(f'<li>{item}</li>' for item in items)
        return f'<ul style="margin: 0 0 8px 18px; padding: 0;">{bullets}</ul>'
    
    @staticmethod
    def heatmap(label: str) -> str:
        """Generate colored recommendation badge"""
        colors = {
            'STRONG BUY': '#27ae60',
            'BUY': '#2ecc71',
            'HOLD': '#f1c40f',
            'SELL': '#e74c3c',
        }
        color = colors.get(label.upper(), '#bdc3c7')
        label_html = '<b>STRONG</b> BUY' if label.upper() == 'STRONG BUY' else label
        
        return (
            f'<div style="display:inline-block;width:130px;height:16px;'
            f'background:{color};border-radius:6px;text-align:center;'
            f'color:#fff;font-weight:bold;line-height:16px;font-size:0.95em;">'
            f'{label_html}</div>'
        )
    
    @staticmethod
    def expand_block(term: str, label: str, bar: str, bullets: str, idx: int) -> str:
        """Create expandable recommendation section"""
        return f'''
        <div style="margin-bottom:18px;">
            <b>{term}: {label}</b><br>
            {bar}
            <a href="#" onclick="var e=document.getElementById('reasons_{idx}');
                if(e.style.display==='none'){{e.style.display='block';this.innerText='Hide reasons';}}
                else{{e.style.display='none';this.innerText='Show reasons';}}
                return false;" style="font-size:0.95em;">Show reasons</a>
            <div id="reasons_{idx}" style="display:none;">{bullets}</div>
        </div>
        '''
    
    @staticmethod
    def format_quote(quote_result: Dict[str, Any]) -> str:
        """Format stock quote data as HTML"""
        if not quote_result or quote_result.get('status') != 'ok':
            return ''
        
        data = quote_result.get('data', {})
        price = data.get('price', 'N/A')
        currency = data.get('currency', '')
        return f'<b>Price:</b> {price} {currency}'


# ============================================================================
# LLM Service
# ============================================================================

class LLMService:
    """Handle communication with LLM providers (Ollama, Gemini)"""
    
    def __init__(self, config: Config):
        self.config = config
    
    def call_ollama(self, prompt: str, model_key: str = 'llama3', timeout: int = 60) -> str:
        """Call Ollama API"""
        model = self.config.MODEL_MAP.get(model_key, 'llama3:8b')
        
        try:
            start_time = time.time()
            response = requests.post(
                self.config.OLLAMA_URL,
                json={
                    'model': model,
                    'messages': [{'role': 'user', 'content': prompt}],
                    'stream': False
                },
                timeout=timeout
            )
            elapsed = time.time() - start_time
            print(f"[Ollama] Model '{model}' response time: {elapsed:.2f}s")
            
            response.raise_for_status()
            return response.json()['message']['content']
        except Exception as e:
            return f"Sorry, {model} (Ollama) could not process your request. ({e})"
    
    def call_gemini(self, prompt: str, timeout: int = 15) -> str:
        """Call Gemini API"""
        if not self.config.GEMINI_API_KEY:
            return "Gemini API key not set. Please set GEMINI_API_KEY in your environment."
        
        try:
            response = requests.post(
                self.config.GEMINI_URL,
                headers={'Content-Type': 'application/json'},
                params={'key': self.config.GEMINI_API_KEY},
                json={
                    'contents': [{'role': 'user', 'parts': [{'text': prompt}]}]
                },
                timeout=timeout
            )
            response.raise_for_status()
            reply = response.json()['candidates'][0]['content']['parts'][0]['text']
            
            # Filter out code/tool responses
            if reply.strip().startswith('```') or 'tool_code' in reply or 'get_stock_info' in reply:
                return "I don't know. Please ask about information shown above or request a different stock."
            
            return reply
        except Exception as e:
            return f"Sorry, Gemini could not process your request. ({e})"
    
    def humanize_response(self, response_html: str, model_key: str = 'llama3') -> str:
        """Make response more conversational using LLM"""
        prompt = (
            "You are a helpful stock market assistant. Only use the information provided below, "
            "which comes from yfinance and internal agents. If you do not know the answer from the "
            "provided information, reply: 'I don't know.' Do not use any outside knowledge or make up answers. "
            "Rewrite the following stock analysis recommendations to sound more human, conversational, "
            "and friendly, but keep ALL the HTML tags and formatting EXACTLY as in the input. "
            "Do NOT remove, escape, or alter any HTML tags.\n\n"
            f"{response_html}"
        )
        
        if self.config.LLM_PROVIDER == 'ollama':
            return self.call_ollama(prompt, model_key)
        else:
            result = self.call_gemini(prompt)
            return result if result and not result.startswith("Sorry") else response_html


# ============================================================================
# Stock Analysis Service
# ============================================================================

class StockService:
    """Coordinate stock analysis operations"""
    
    def __init__(self):
        self.company_search = CompanySearch()
        self.yahoo_agent = YahooFinanceAgent()
        self.analysis_agent = StockAnalysisAgent()
        self.rss_news_agent = RSSNewsAgent()
        self.formatter = HTMLFormatter()
    
    def search_company(self, company_name: str) -> Optional[Dict[str, Any]]:
        """Search for company and return best match"""
        search_result = self.company_search.analyze(company_name)
        
        # Handle ToolResult return type
        if hasattr(search_result, 'data'):
            matches = search_result.data.get('matches', []) if search_result.data else []
        else:
            # Backward compatibility
            matches = search_result.get('matches', [])
        
        return matches[0] if matches else None
    
    def get_stock_analysis(self, ticker: str, company_name: str) -> Dict[str, Any]:
        """Get complete stock analysis including quote, recommendations, and news"""
        # Get quote data
        quote_result = self.yahoo_agent.handle({
            "action": "get_quote",
            "parameters": {"ticker": ticker}
        })
        
        # Get recommendations
        recommendations = self.analysis_agent.get_recommendation(ticker)
        
        # Get news (handle ToolResult return type)
        news_result_obj = self.rss_news_agent.analyze(ticker)
        if hasattr(news_result_obj, 'data'):
            news_result = news_result_obj.data if news_result_obj.data else {'news': []}
        else:
            news_result = news_result_obj  # Backward compatibility
        
        # Get historical price data for chart (30 days)
        price_history = self.get_price_history(ticker, period='1mo')
        
        return {
            'ticker': ticker,
            'company_name': company_name,
            'quote': quote_result,
            'recommendations': recommendations,
            'news': news_result,
            'price_history': price_history
        }
    
    def get_price_history(self, ticker: str, period: str = '1mo') -> Dict[str, List]:
        """Fetch historical price data for charting"""
        import yfinance as yf
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period=period)
            
            if hist.empty:
                return {'dates': [], 'prices': []}
            
            # Convert to lists for JSON serialization
            dates = [date.strftime('%Y-%m-%d') for date in hist.index]
            prices = hist['Close'].round(2).tolist()
            
            return {'dates': dates, 'prices': prices}
        except Exception as e:
            print(f"Error fetching price history for {ticker}: {e}")
            return {'dates': [], 'prices': []}
    
    def format_analysis_html(self, analysis: Dict[str, Any]) -> str:
        """Format analysis data as HTML"""
        # Extract data
        ticker = analysis['ticker']
        company_name = analysis['company_name']
        recommendations = analysis['recommendations']
        price_history = analysis.get('price_history', {'dates': [], 'prices': []})
        
        # Format quote
        quote_html = self.formatter.format_quote(analysis['quote'])
        
        # Format price info (only if we have price data)
        price_table_html = ''
        if price_history['dates'] and price_history['prices']:
            # Calculate 30-day change
            first_price = price_history['prices'][0]
            last_price = price_history['prices'][-1]
            overall_change = last_price - first_price
            overall_change_pct = (overall_change / first_price) * 100
            change_color = '#10b981' if overall_change >= 0 else '#ef4444'
            change_symbol = '+' if overall_change >= 0 else ''
            
            price_table_html = f'''
            <div style="margin:15px 0;padding:12px 15px;background:#f9fafb;border-left:3px solid {change_color};border-radius:4px;">
                <b>30-Day Performance:</b> 
                <span style="color:{change_color};font-weight:600;">
                    {change_symbol}{overall_change_pct:.2f}% ({change_symbol}${overall_change:.2f})
                </span>
            </div>
            '''
        
        # Format news
        news_html = self._format_news_html(analysis['news'])
        
        # Format recommendations
        recommendations_html = self._format_recommendations_html(recommendations)
        
        # Combine all sections
        return (
            f"<b>{company_name} ({ticker})</b><br>"
            f"{quote_html}<br>"
            f"{price_table_html}"
            f"{news_html}"
            f"{recommendations_html}"
        )
    
    def _format_news_html(self, news_result: Dict[str, Any]) -> str:
        """Format news section"""
        if not news_result.get('news'):
            return ''
        
        news_items = ''.join(
            f'<li><a href="{item["url"]}" target="_blank">{item["headline"]}</a></li>'
            for item in news_result['news'] if item.get('headline')
        )
        return f'<br><b>Recent News:</b><ul style="margin:8px 0 8px 18px;">{news_items}</ul>'
    
    def _format_recommendations_html(self, recommendations: Dict[str, Any]) -> str:
        """Format recommendations section"""
        short = recommendations.get('short_term', {})
        medium = recommendations.get('medium_term', {})
        long = recommendations.get('long_term', {})
        
        blocks = [
            self.formatter.expand_block(
                'Short-term (1 week)',
                short.get('label', 'N/A'),
                self.formatter.heatmap(short.get('label', 'N/A')),
                self.formatter.to_bullets(self.formatter.add_tooltips(short.get('summary', ''))),
                1
            ),
            self.formatter.expand_block(
                'Medium-term (3 months)',
                medium.get('label', 'N/A'),
                self.formatter.heatmap(medium.get('label', 'N/A')),
                self.formatter.to_bullets(self.formatter.add_tooltips(medium.get('summary', ''))),
                2
            ),
            self.formatter.expand_block(
                'Long-term (6-12 months)',
                long.get('label', 'N/A'),
                self.formatter.heatmap(long.get('label', 'N/A')),
                self.formatter.to_bullets(self.formatter.add_tooltips(long.get('summary', ''))),
                3
            )
        ]
        
        return f"<b>Time Horizon Recommendations:</b><br><br>{''.join(blocks)}"
    
    def get_earnings_data(self, ticker: str) -> Dict[str, Any]:
        """Get earnings data for ticker"""
        return self.yahoo_agent.handle({
            "action": "get_earnings",
            "parameters": {"ticker": ticker}
        })


# ============================================================================
# Flask Application
# ============================================================================

app = Flask(__name__, static_folder='.', static_url_path='')
app.secret_key = Config.SECRET_KEY

# Initialize services
config = Config()
llm_service = LLMService(config)
stock_service = StockService()


@app.route('/')
def index():
    """Serve the main HTML page"""
    try:
        html_path = os.path.join(os.path.dirname(__file__), 'index.html')
        with open(html_path, 'r', encoding='utf-8') as f:
            content = f.read()
        from flask import Response
        return Response(content, mimetype='text/html')
    except Exception as e:
        print(f"Error serving index.html: {e}")
        return f"Error loading page: {e}", 500


@app.route('/chat', methods=['POST'])
def chat():
    """Handle chat messages and stock queries"""
    data = request.get_json()
    history = data.get('history', [])
    model_key = data.get('model', 'llama3')
    
    if not history:
        return jsonify({'reply': 'Please ask about a stock or company.'})
    
    user_message = history[-1]['content']
    
    # Handle earnings queries
    if 'earnings' in user_message.lower():
        return handle_earnings_query(user_message, history)
    
    # Handle initial stock query
    if len(history) == 1 or not session.get('analysis_context'):
        return handle_stock_query(user_message, model_key)
    
    # Handle news article queries
    news_articles = session.get('last_news_articles', [])
    matched_article = find_matching_article(user_message, news_articles)
    if matched_article:
        return handle_news_article_query(matched_article, model_key)
    
    # Handle general follow-up questions
    return handle_followup_query(user_message, model_key)


def handle_stock_query(company_name: str, model_key: str) -> Dict:
    """Handle initial stock analysis query"""
    # Search for company
    match = stock_service.search_company(company_name)
    if not match:
        return jsonify({'reply': f"No matching companies found for '{company_name}'."})
    
    # Get analysis
    ticker = match['symbol']
    company_full_name = match['long_name'] or match['short_name']
    analysis = stock_service.get_stock_analysis(ticker, company_full_name)
    
    # Format HTML
    result_html = stock_service.format_analysis_html(analysis)
    
    # Store in session
    session['analysis_context'] = result_html
    session['last_news_articles'] = analysis['news'].get('news', [])
    
    return jsonify({'reply': result_html})


def handle_earnings_query(user_message: str, history: List) -> Dict:
    """Handle earnings-specific queries"""
    # Extract ticker from context
    ticker = extract_ticker_from_context(session.get('analysis_context', ''), history)
    if not ticker:
        return jsonify({'reply': "Could not determine ticker for earnings lookup."})
    
    # Get earnings data
    earnings_result = stock_service.get_earnings_data(ticker)
    if earnings_result.get('status') != 'ok':
        return jsonify({'reply': f"Could not fetch earnings for {ticker}."})
    
    # Format earnings HTML
    earnings_html = format_earnings_html(ticker, earnings_result['data'])
    return jsonify({'reply': earnings_html})


def handle_news_article_query(article: Dict, model_key: str) -> Dict:
    """Handle news article summarization"""
    article_url = article.get('url', '')
    article_content = fetch_article_text(article_url) if article_url else ''
    
    article_text = (
        f"Headline: {article.get('headline', '')}\n"
        f"URL: {article_url}\n"
        f"Summary: {article.get('summary', '')}\n"
        f"Content: {article_content}"
    )
    
    prompt = (
        f"Here is a news article about a stock. Please summarize it in 2-3 sentences "
        f"for a general audience.\n{article_text}\nIf you don't have enough information, say so."
    )
    
    if config.LLM_PROVIDER == 'ollama':
        reply = llm_service.call_ollama(prompt, model_key)
    else:
        reply = llm_service.call_gemini(prompt)
    
    return jsonify({'reply': reply})


def handle_followup_query(user_message: str, model_key: str) -> Dict:
    """Handle general follow-up questions, including multi-stock comparisons"""
    context = session.get('analysis_context', '')
    
    # Check if user is asking about a different stock
    additional_stock_data = detect_and_fetch_additional_stocks(user_message, context)
    
    # Build enhanced context if we found additional stocks
    enhanced_context = context
    instruction_suffix = ""
    
    if additional_stock_data:
        enhanced_context += "\n\n<b>Additional Stock Data (for comparison):</b><br>" + additional_stock_data
        instruction_suffix = (
            "\n\nIMPORTANT: I have fetched REAL DATA for the additional stock mentioned in the question. "
            "This data is shown in the 'Additional Stock Data' section above. "
            "USE THIS DATA DIRECTLY in your answer - do NOT suggest the user look it up elsewhere. "
            "Extract the specific metrics requested (PE ratio, price, market cap, etc.) from the data provided "
            "and present them clearly in your response."
        )
    
    prompt = (
        f"Here is the stock analysis context for reference (from yfinance and internal agents):\n{enhanced_context}\n\n"
        f"Now answer the user's question: {user_message}\n\n"
        f"IMPORTANT: Format your response with HTML tags for better readability:\n"
        f"- Use <b>text</b> for bold important terms\n"
        f"- Use <br> for line breaks\n"
        f"- Use numbered lists like: 1. <b>Item</b>: Description<br>\n"
        f"- Keep your response clear and well-formatted with HTML.\n"
        f"- If comparing multiple stocks, present the comparison clearly with specific numbers."
        f"{instruction_suffix}"
    )
    
    if config.LLM_PROVIDER == 'ollama':
        reply = llm_service.call_ollama(prompt, model_key)
    else:
        reply = llm_service.call_gemini(prompt)
    
    return jsonify({'reply': reply})


def find_matching_article(user_message: str, news_articles: List) -> Optional[Dict]:
    """Find news article matching user's query"""
    if not news_articles:
        return None
    
    # Try index-based matching (first, second, etc.)
    idx_match = re.search(
        r'(first|second|third|fourth|fifth|[0-9]+)[^\w]*(news|article|headline)',
        user_message,
        re.IGNORECASE
    )
    
    if idx_match:
        idx_map = {'first': 0, 'second': 1, 'third': 2, 'fourth': 3, 'fifth': 4}
        idx_str = idx_match.group(1).lower()
        idx = idx_map.get(idx_str)
        
        if idx is None:
            try:
                idx = int(idx_str) - 1
            except:
                idx = None
        
        if idx is not None and 0 <= idx < len(news_articles):
            return news_articles[idx]
    
    # Try headline matching
    for article in news_articles:
        if article.get('headline') and article['headline'].lower() in user_message.lower():
            return article
    
    return None


def extract_ticker_from_context(context: str, history: List) -> Optional[str]:
    """Extract ticker symbol from context or history"""
    # Try context first
    match = re.search(r'\(([^)]+)\)', context)
    if match:
        return match.group(1)
    
    # Try history
    for msg in reversed(history):
        text = msg.get('content', '')
        match = re.search(r'\(([^)]+)\)', text)
        if match:
            return match.group(1)
    
    return None


def detect_and_fetch_additional_stocks(user_message: str, current_context: str) -> str:
    """
    Detect if user is asking about a different stock and fetch its data.
    Returns HTML-formatted data for the additional stock(s).
    """
    # Extract current ticker from context
    current_ticker = None
    match = re.search(r'\(([A-Z]{1,5})\)', current_context)
    if match:
        current_ticker = match.group(1)
    
    # Look for potential ticker symbols or company names in the message
    # Common patterns: "AAPL", "Apple", "compare with MSFT", "what about GOOGL"
    potential_tickers = []
    
    # Pattern 1: Direct ticker symbols (1-5 uppercase letters)
    ticker_matches = re.findall(r'\b([A-Z]{2,5})\b', user_message)
    for ticker in ticker_matches:
        if ticker != current_ticker and ticker not in ['PE', 'EPS', 'ROE', 'ROA']:  # Avoid metric acronyms
            potential_tickers.append(ticker)
    
    # Pattern 2: Company names in various question patterns
    company_patterns = [
        r'(?:PE|price.*earnings|P/E).*?(?:ratio|for)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',  # "PE ratio for Apple"
        r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)(?:\'s|s)?\s+(?:PE|price.*earnings|P/E)',  # "Apple's PE ratio"
        r'(?:compare (?:with|to|against)|what about|how about)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
        r'(?:vs|versus)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
        r'(?:get|fetch|show|tell me)\s+.*?(?:for|of)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',  # "get PE for Apple"
    ]
    
    for pattern in company_patterns:
        company_matches = re.findall(pattern, user_message, re.IGNORECASE)
        for company_name in company_matches:
            company_name = company_name.strip()
            # Try direct ticker first
            if len(company_name) <= 5 and company_name.upper() == company_name:
                if company_name.upper() != current_ticker:
                    potential_tickers.append(company_name.upper())
            else:
                # Try to resolve company name to ticker
                match = stock_service.search_company(company_name)
                if match:
                    ticker = match['symbol']
                    if ticker != current_ticker:
                        potential_tickers.append(ticker)
    
    # Fetch data for additional tickers
    if not potential_tickers:
        return ""
    
    additional_data_parts = []
    for ticker in potential_tickers[:3]:  # Limit to 3 additional stocks
        try:
            # Get basic quote and info
            quote_result = stock_service.yahoo_agent.get_quote(ticker)
            
            if quote_result.get('status') == 'ok':
                quote_data = quote_result.get('data', {})
                
                # Try to get additional fundamental data using yfinance directly
                import yfinance as yf
                stock = yf.Ticker(ticker)
                info = stock.info
                
                # Extract key metrics
                pe_ratio = info.get('trailingPE', info.get('forwardPE', 'N/A'))
                market_cap = info.get('marketCap', 'N/A')
                if market_cap != 'N/A':
                    market_cap = f"${market_cap / 1e9:.2f}B" if market_cap >= 1e9 else f"${market_cap / 1e6:.2f}M"
                
                dividend_yield = info.get('dividendYield', 'N/A')
                if dividend_yield != 'N/A':
                    dividend_yield = f"{dividend_yield * 100:.2f}%"
                
                eps = info.get('trailingEps', 'N/A')
                revenue = info.get('totalRevenue', 'N/A')
                if revenue != 'N/A':
                    revenue = f"${revenue / 1e9:.2f}B" if revenue >= 1e9 else f"${revenue / 1e6:.2f}M"
                
                profit_margin = info.get('profitMargins', 'N/A')
                if profit_margin != 'N/A':
                    profit_margin = f"{profit_margin * 100:.2f}%"
                
                # Format PE ratio prominently
                pe_display = f"<b style='font-size:1.1em;color:#2563eb;'>{pe_ratio:.2f}</b>" if isinstance(pe_ratio, (int, float)) else pe_ratio
                
                # Format the additional stock data with clear sections
                stock_html = f"""
<div style="margin:15px 0;padding:15px;background:#f0f9ff;border-left:4px solid #3b82f6;border-radius:6px;box-shadow:0 2px 4px rgba(0,0,0,0.1);">
    <div style="font-size:1.1em;margin-bottom:10px;"><b>{info.get('longName', ticker)} ({ticker})</b></div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
        <div><b>Current Price:</b> ${quote_data.get('price', 'N/A')} {quote_data.get('currency', '')}</div>
        <div><b>P/E Ratio:</b> {pe_display}</div>
        <div><b>Market Cap:</b> {market_cap}</div>
        <div><b>EPS:</b> {eps if eps != 'N/A' else 'N/A'}</div>
        <div><b>Revenue:</b> {revenue}</div>
        <div><b>Profit Margin:</b> {profit_margin}</div>
        <div><b>Dividend Yield:</b> {dividend_yield}</div>
    </div>
</div>
"""
                additional_data_parts.append(stock_html)
        except Exception as e:
            print(f"Error fetching data for {ticker}: {e}")
            continue
    
    return ''.join(additional_data_parts)


def format_earnings_html(ticker: str, data: Dict) -> str:
    """Format earnings data as HTML table"""
    html = f"<b>Earnings for {ticker}:</b><br>"
    
    # Next earnings
    next_earnings = data.get('next_earnings')
    if next_earnings:
        html += "<b>Next Earnings Event:</b><ul>"
        for k, v in next_earnings.items():
            html += f"<li><b>{k}:</b> {v}</li>"
        html += "</ul>"
    
    # Earnings history
    earnings_history = data.get('earnings_history', [])
    if earnings_history:
        # Determine date column
        columns = list(earnings_history[0].keys())
        date_col = next((k for k in ['Earnings Date', 'index', 'date'] if k in columns), columns[0])
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
    
    return html


if __name__ == '__main__':
    app.run(debug=True, port=5000)

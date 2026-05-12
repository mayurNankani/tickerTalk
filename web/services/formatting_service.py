"""
Formatting Service
HTML formatting utilities for stock analysis display
"""

import re
import time
from datetime import datetime
from typing import Dict, Any
from src.tools.web_search import normalize_result_url


# Tooltip definitions
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


class FormattingService:
    """Utilities for formatting analysis data as HTML"""

    @staticmethod
    def _clean_reason_summary(summary: str, section: str) -> str:
        """Normalize generic fallback text so each section keeps its own meaning."""
        text = (summary or '').strip()
        if not text:
            return ''

        generic_technical = 'No strong technical signals detected.'
        generic_fundamental = 'No strong fundamental signals detected.'

        lowered = text.lower()
        if lowered == generic_technical.lower():
            if section == 'technical':
                return text
            return f'No strong {section} signals detected.'

        if lowered == generic_fundamental.lower():
            if section == 'fundamental':
                return text
            return f'No strong {section} signals detected.'

        return text
    
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
        return f'<ul>{bullets}</ul>'
    
    @staticmethod
    def heatmap(label: str) -> str:
        """Generate colored recommendation badge"""
        label = (label or 'N/A').upper()
        class_map = {
            'STRONG BUY': 'badge-strong-buy',
            'BUY':        'badge-buy',
            'HOLD':       'badge-hold',
            'SELL':       'badge-sell',
        }
        icon_map = {
            'STRONG BUY': '▲▲',
            'BUY':        '▲',
            'HOLD':       '◆',
            'SELL':       '▼',
        }
        css_class = class_map.get(label, 'badge-na')
        icon = icon_map.get(label, '—')
        return f'<span class="badge {css_class}">{icon} {label}</span>'
    
    def expand_block(self, term: str, label: str, bar: str, bullets: str, idx: int, 
                     fundamental_summary: str = None, technical_summary: str = None, sentiment_summary: str = None) -> str:
        """Create expandable recommendation section with separate fundamental, technical, and sentiment reasons"""
        
        sections = []
        
        if fundamental_summary:
            fund_bullets = self.to_bullets(self.add_tooltips(fundamental_summary))
            sections.append(f'<div class="reason-group reason-fundamental"><span class="reason-group-label">Fundamental</span>{fund_bullets}</div>')
        
        if technical_summary:
            tech_bullets = self.to_bullets(self.add_tooltips(technical_summary))
            sections.append(f'<div class="reason-group reason-technical"><span class="reason-group-label">Technical</span>{tech_bullets}</div>')
        
        if sentiment_summary:
            sentiment_bullets = self.to_bullets(self.add_tooltips(sentiment_summary))
            sections.append(f'<div class="reason-group reason-sentiment"><span class="reason-group-label">Sentiment</span>{sentiment_bullets}</div>')
        
        # Build reasons HTML
        reasons_html = (
            f'<div class="reasons-body">{" ".join(sections)}</div>'
            if sections else
            f'<div class="reasons-body">{bullets}</div>'
        )
        
        return f'''
        <div class="rec-row">
            <div>
                <div class="rec-label">{term}</div>
                <details class="rec-details">
                    <summary>Reasons</summary>
                    {reasons_html}
                </details>
            </div>
            {bar}
        </div>
        '''
    
    def format_analysis_html(self, analysis) -> str:
        """
        Format complete analysis as HTML
        
        Args:
            analysis: StockAnalysis dataclass object
            
        Returns:
            HTML string for chat rendering
        """
        ticker = getattr(analysis, 'ticker', '') or 'N/A'
        company_name = getattr(analysis, 'company_name', '') or ticker
        quote = getattr(analysis, 'quote', {}) or {}
        recommendations = getattr(analysis, 'recommendations', {}) or {}
        news_result = getattr(analysis, 'news', {}) or {}
        price_history = getattr(analysis, 'price_history', {}) or {}

        display_name = self._safe_call(
            self._get_display_name,
            company_name,
            quote,
            fallback=company_name,
        )

        logo_html = ''
        if ticker != 'N/A':
            logo_html = self._safe_call(self._format_logo, ticker, fallback='')

        price_html = self._safe_call(self._format_price_line, quote, fallback='')
        price_chart_html = self._safe_call(
            self._format_price_chart,
            ticker,
            price_history,
            fallback='',
        )
        news_html = self._safe_call(self._format_news, news_result, fallback='')
        recommendations_html = self._safe_call(
            self._format_recommendations,
            recommendations,
            fallback='',
        )

        return (
            f"<div class='analysis-block stock-card' data-ticker='{ticker}'>"
            f"<div class='stock-card-header'>"
            f"{logo_html}"
            f"<div>"
            f"<div class='stock-name'>{display_name}<span class='stock-ticker-badge'>{ticker}</span></div>"
            f"<div class='stock-price-line'>{price_html}</div>"
            f"</div>"
            f"</div>"
            f"{price_chart_html}"
            f"{recommendations_html}"
            f"{news_html}"
            f"</div>"
        )

    @staticmethod
    def _safe_call(fn, *args, fallback=''):
        """Run formatter step defensively so one bad field doesn't drop the whole card."""
        try:
            return fn(*args)
        except Exception:
            return fallback
    
    def _format_logo(self, ticker: str) -> str:
        """Format company logo using Finnhub logo API"""
        logo_url = f"https://finnhub.io/api/logo?symbol={ticker}"
        return (
            f'<img src="{logo_url}" alt="{ticker}" class="stock-logo" '
            f'onerror="this.style.display=\'none\'"/>'
        )
    
    def _get_display_name(self, company_name: str, quote: Dict[str, Any]) -> str:
        """Get best display name from quote data"""
        try:
            qdata = quote.get('data', {}) if isinstance(quote, dict) else {}
            longname = qdata.get('name') or qdata.get('shortName') or qdata.get('longName')
            if longname and longname.strip():
                return longname
        except Exception:
            pass
        return company_name
    
    def _format_price_line(self, quote: Dict[str, Any]) -> str:
        """Format current price line with data freshness timestamp"""
        try:
            qdata = quote.get('data', {}) if isinstance(quote, dict) else {}
            price = qdata.get('price')
            currency = qdata.get('currency', '')

            if price is not None and price != 'N/A':
                try:
                    price_val = float(price)
                    price_text = f"${price_val:,.2f}"
                except Exception:
                    price_text = str(price)

                fetched_at = datetime.now().strftime('%b %d, %H:%M')
                return (
                    f"<span style='font-size:0.95em;color:#6b7280;'>"
                    f"{price_text} {currency}"
                    f"<span title='Data fetched at {fetched_at}' "
                    f"style='margin-left:6px;font-size:0.85em;color:#9ca3af;cursor:help;'>"
                    f"&#128337; {fetched_at}</span>"
                    f"</span>"
                )
        except Exception:
            pass

        return ''
    
    def _format_price_chart(self, ticker: str, price_history: Dict[str, Any]) -> str:
        """Format price chart section"""
        if not isinstance(price_history, dict):
            return ''

        dates = price_history.get('dates') or []
        prices_raw = price_history.get('prices') or []
        if not dates or not prices_raw:
            return ''

        valid_prices = []
        for p in prices_raw:
            try:
                if p is not None:
                    valid_prices.append(float(p))
            except Exception:
                continue

        if not valid_prices:
            return ''
        first_price = valid_prices[0]
        last_price = valid_prices[-1]
        overall_change = last_price - first_price
        overall_change_pct = (overall_change / first_price) * 100 if first_price else 0.0
        change_color = '#10b981' if overall_change >= 0 else '#ef4444'
        change_symbol = '+' if overall_change >= 0 else ''
        perf_class = 'positive' if overall_change >= 0 else 'negative'
        
        chart_id = f"chart_{ticker.replace('.', '_')}_{int(time.time() * 1000)}"
        
        return f'''
        <div class="perf-bar {perf_class}">
            <span>
                <b>30-Day:</b>
                <span style="color:{change_color};font-weight:600;">
                    {change_symbol}{overall_change_pct:.2f}% ({change_symbol}${overall_change:.2f})
                </span>
            </span>
            <button class="toggle-chart-btn" data-chart-id="{chart_id}" data-ticker="{ticker}">
                <span id="btn_{chart_id}">Show Chart ▼</span>
            </button>
        </div>
        <div id="{chart_id}" class="chart-container" style="display:none;">
            <div style="display:flex;justify-content:center;margin-bottom:0.75rem;">
                <div class="period-control">
                    <button class="period-btn" data-period="1d" data-ticker="{ticker}" data-chart-id="{chart_id}">1D</button>
                    <button class="period-btn" data-period="5d" data-ticker="{ticker}" data-chart-id="{chart_id}">5D</button>
                    <button class="period-btn active" data-period="1mo" data-ticker="{ticker}" data-chart-id="{chart_id}">1M</button>
                </div>
            </div>
            <canvas id="canvas_{chart_id}" style="width:100%;height:250px;"></canvas>
            <div id="loading_{chart_id}" style="text-align:center;padding:20px;color:var(--text-3,#64748b);display:none;">Loading chart...</div>
        </div>
        '''
    
    def _format_news(self, news_result: Dict[str, Any]) -> str:
        """Format news section"""
        articles = []
        if isinstance(news_result, dict):
            articles = news_result.get('news') or []
        elif isinstance(news_result, list):
            articles = news_result

        if not articles:
            return ''

        valid_articles = [
            item for item in articles
            if isinstance(item, dict) and item.get('headline') and item.get('url')
        ]
        if not valid_articles:
            return ''

        def _render_cards(items):
            return ''.join(
                f'<a href="{normalize_result_url(item["url"])}" target="_blank" rel="noopener" class="news-card">'
                f'<div class="news-card-headline">{item["headline"]}</div>'
                f'<div class="news-card-meta">View article \u2192</div>'
                f'</a>'
                for item in items
            )

        top_articles = valid_articles[:5]
        remaining_articles = valid_articles[5:]
        top_items_html = _render_cards(top_articles)

        more_html = ''
        if remaining_articles:
            remaining_count = len(remaining_articles)
            remaining_items_html = _render_cards(remaining_articles)
            more_html = (
                f"<div class='news-more-wrap'>"
                f"<div class='news-more-content' style='display:none;'>{remaining_items_html}</div>"
                f"<button type='button' class='news-more-btn' "
                f"onclick=\"const content=this.previousElementSibling; const show=content.style.display==='none'; content.style.display=show?'block':'none'; this.textContent=show?'Hide extra news':'View all news ({remaining_count})';\">"
                f"View all news ({remaining_count})"
                f"</button>"
                f"</div>"
            )

        return (
            f'<div class="news-section-title">Recent News</div>'
            f'<div>{top_items_html}{more_html}</div>'
        )
    
    def _format_recommendations(self, recommendations: Dict[str, Any]) -> str:
        """Format recommendations section"""
        if not isinstance(recommendations, dict):
            return ''

        short = recommendations.get('short_term') or {}
        medium = recommendations.get('medium_term') or {}
        long = recommendations.get('long_term') or {}
        fundamental = recommendations.get('fundamental') or {}
        technical = recommendations.get('technical') or {}
        sentiment = recommendations.get('sentiment') or {}
        
        # Extract fundamental, technical, and sentiment summaries
        fund_summary = str(fundamental.get('summary', '') or '')
        tech_summary = str(technical.get('summary', '') or '')
        sentiment_summary = str(sentiment.get('summary', '') or '')
        
        # Parse short-term summary (technical + sentiment)
        short_summary = str(short.get('summary', '') or '')
        short_tech = ''
        short_sentiment = ''
        
        if '|' in short_summary:
            parts = short_summary.split('|')
            for part in parts:
                part = part.strip()
                if part.startswith('Technical:'):
                    short_tech = part.replace('Technical:', '').strip()
                elif part.startswith('Sentiment:'):
                    short_sentiment = part.replace('Sentiment:', '').strip()

        short_tech = self._clean_reason_summary(short_tech or short_summary, 'technical')
        short_sentiment = self._clean_reason_summary(short_sentiment, 'sentiment')
        
        # Parse medium-term summary (fundamental + technical + sentiment)
        medium_summary = str(medium.get('summary', '') or '')
        medium_fund = ''
        medium_tech = ''
        medium_sentiment = ''
        
        if '|' in medium_summary:
            parts = medium_summary.split('|')
            for part in parts:
                part = part.strip()
                if part.startswith('Fundamentals:'):
                    medium_fund = part.replace('Fundamentals:', '').strip()
                elif part.startswith('Technical:'):
                    medium_tech = part.replace('Technical:', '').strip()
                elif part.startswith('Sentiment:'):
                    medium_sentiment = part.replace('Sentiment:', '').strip()

        if not (medium_fund or medium_tech or medium_sentiment) and medium_summary:
            medium_tech = medium_summary

        medium_fund = self._clean_reason_summary(medium_fund, 'fundamental')
        medium_tech = self._clean_reason_summary(medium_tech, 'technical')
        medium_sentiment = self._clean_reason_summary(medium_sentiment, 'sentiment')
        
        # Parse long-term summary (fundamental + technical + sentiment)
        long_summary = str(long.get('summary', '') or '')
        long_fund = ''
        long_tech = ''
        long_sentiment = ''
        
        if '|' in long_summary:
            parts = long_summary.split('|')
            for part in parts:
                part = part.strip()
                if part.startswith('Fundamentals:'):
                    long_fund = part.replace('Fundamentals:', '').strip()
                elif part.startswith('Technical:'):
                    long_tech = part.replace('Technical:', '').strip()
                elif part.startswith('Sentiment:'):
                    long_sentiment = part.replace('Sentiment:', '').strip()

        if not (long_fund or long_tech or long_sentiment) and long_summary:
            long_tech = long_summary

        long_fund = self._clean_reason_summary(long_fund, 'fundamental')
        long_tech = self._clean_reason_summary(long_tech, 'technical')
        long_sentiment = self._clean_reason_summary(long_sentiment, 'sentiment')
        
        blocks = [
            self.expand_block(
                'Short-term (1 week)',
                short.get('label', 'N/A'),
                self.heatmap(short.get('label', 'N/A')),
                '',  # bullets placeholder
                1,
                fundamental_summary='',
                technical_summary=short_tech,
                sentiment_summary=short_sentiment
            ),
            self.expand_block(
                'Medium-term (3 months)',
                medium.get('label', 'N/A'),
                self.heatmap(medium.get('label', 'N/A')),
                '',  # bullets placeholder
                2,
                fundamental_summary=medium_fund,
                technical_summary=medium_tech,
                sentiment_summary=medium_sentiment
            ),
            self.expand_block(
                'Long-term (6-12 months)',
                long.get('label', 'N/A'),
                self.heatmap(long.get('label', 'N/A')),
                '',  # bullets placeholder
                3,
                fundamental_summary=long_fund,
                technical_summary=long_tech,
                sentiment_summary=long_sentiment  # Only show if explicitly in long-term summary (not fallback)
            )
        ]
        
        return f"<div class='rec-section'><div class='rec-section-title'>Time Horizon Recommendations</div>{''.join(blocks)}</div>"
    
    @staticmethod
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
            columns = list(earnings_history[0].keys())
            date_col = 'date' if 'date' in columns else columns[0]
            
            html += "<b>Recent Earnings History:</b>"
            html += '<table border="1" style="border-collapse:collapse;margin-top:10px;"><thead><tr>'
            for col in columns:
                html += f"<th style='padding:8px;background:#f3f4f6;'>{col}</th>"
            html += "</tr></thead><tbody>"
            
            for record in earnings_history[:5]:
                html += "<tr>"
                for col in columns:
                    html += f"<td style='padding:8px;'>{record.get(col, '')}</td>"
                html += "</tr>"
            
            html += "</tbody></table>"
        
        return html

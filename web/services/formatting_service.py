"""
Formatting Service
HTML formatting utilities for stock analysis display
"""

import re
import time
from typing import Dict, Any


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
    
    def format_analysis_html(self, analysis) -> str:
        """
        Format complete analysis as HTML
        
        Args:
            analysis: StockAnalysis dataclass object
            
        Returns:
            HTML formatted analysis
        """
        # Handle both dict and StockAnalysis object
        if hasattr(analysis, 'ticker'):
            # It's a StockAnalysis object
            ticker = analysis.ticker
            company_name = analysis.company_name
            quote = analysis.quote
            recommendations = analysis.recommendations
            price_history = analysis.price_history if hasattr(analysis, 'price_history') else {'dates': [], 'prices': []}
            news = analysis.news
        else:
            # Legacy dict format
            ticker = analysis['ticker']
            company_name = analysis['company_name']
            quote = analysis['quote']
            recommendations = analysis['recommendations']
            price_history = analysis.get('price_history', {'dates': [], 'prices': []})
            news = analysis['news']
        
        # Build header with company name
        display_name = self._get_display_name(company_name, quote)
        price_html = self._format_price_line(quote)
        price_chart_html = self._format_price_chart(ticker, price_history)
        news_html = self._format_news(news)
        recommendations_html = self._format_recommendations(recommendations)
        
        return (
            f"<b>{display_name}</b><br>"
            f"{price_html}<br>"
            f"{price_chart_html}"
            f"{news_html}"
            f"{recommendations_html}"
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
        """Format current price line"""
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
                
                return f"<div><b>Price:</b> {price_text} {currency}</div>"
        except Exception:
            pass
        
        return ''
    
    def _format_price_chart(self, ticker: str, price_history: Dict[str, Any]) -> str:
        """Format price chart section"""
        if not price_history.get('dates') or not price_history.get('prices'):
            return ''
        
        first_price = price_history['prices'][0]
        last_price = price_history['prices'][-1]
        overall_change = last_price - first_price
        overall_change_pct = (overall_change / first_price) * 100
        change_color = '#10b981' if overall_change >= 0 else '#ef4444'
        change_symbol = '+' if overall_change >= 0 else ''
        
        chart_id = f"chart_{ticker.replace('.', '_')}_{int(time.time() * 1000)}"
        
        return f'''
        <div style="margin:15px 0;padding:12px 15px;background:#f9fafb;border-left:3px solid {change_color};border-radius:4px;">
            <div style="display:flex;justify-content:space-between;align-items:center;">
                <div>
                    <b>30-Day Performance:</b> 
                    <span style="color:{change_color};font-weight:600;">
                        {change_symbol}{overall_change_pct:.2f}% ({change_symbol}${overall_change:.2f})
                    </span>
                </div>
                <button class="toggle-chart-btn" data-chart-id="{chart_id}" data-ticker="{ticker}" style="padding:6px 12px;background:#3b82f6;color:white;border:none;border-radius:4px;cursor:pointer;font-size:0.9em;">
                    <span class="btn-text" id="btn_{chart_id}">Show Chart ▼</span>
                </button>
            </div>
            
            <div id="{chart_id}" style="display:none;margin-top:15px;padding-top:15px;border-top:1px solid #e5e7eb;">
                <div style="display:flex;gap:8px;margin-bottom:10px;justify-content:center;">
                    <button class="period-btn" data-period="1d" data-ticker="{ticker}" data-chart-id="{chart_id}" style="padding:6px 14px;background:#e5e7eb;border:1px solid #d1d5db;border-radius:4px;cursor:pointer;font-size:0.85em;">1D</button>
                    <button class="period-btn" data-period="5d" data-ticker="{ticker}" data-chart-id="{chart_id}" style="padding:6px 14px;background:#e5e7eb;border:1px solid #d1d5db;border-radius:4px;cursor:pointer;font-size:0.85em;">5D</button>
                    <button class="period-btn active" data-period="1mo" data-ticker="{ticker}" data-chart-id="{chart_id}" style="padding:6px 14px;background:#3b82f6;color:white;border:1px solid #3b82f6;border-radius:4px;cursor:pointer;font-size:0.85em;">1M</button>
                </div>
                <canvas id="canvas_{chart_id}" style="width:100%;max-width:600px;height:250px;margin:0 auto;display:block;"></canvas>
                <div id="loading_{chart_id}" style="text-align:center;padding:20px;color:#666;display:none;">Loading chart...</div>
            </div>
        </div>
        '''
    
    def _format_news(self, news_result: Dict[str, Any]) -> str:
        """Format news section"""
        if not news_result.get('news'):
            return ''
        
        news_items = ''.join(
            f'<li><a href="{item["url"]}" target="_blank">{item["headline"]}</a></li>'
            for item in news_result['news'] if item.get('headline')
        )
        return f'<br><b>Recent News:</b><ul style="margin:8px 0 8px 18px;">{news_items}</ul>'
    
    def _format_recommendations(self, recommendations: Dict[str, Any]) -> str:
        """Format recommendations section"""
        short = recommendations.get('short_term', {})
        medium = recommendations.get('medium_term', {})
        long = recommendations.get('long_term', {})
        
        blocks = [
            self.expand_block(
                'Short-term (1 week)',
                short.get('label', 'N/A'),
                self.heatmap(short.get('label', 'N/A')),
                self.to_bullets(self.add_tooltips(short.get('summary', ''))),
                1
            ),
            self.expand_block(
                'Medium-term (3 months)',
                medium.get('label', 'N/A'),
                self.heatmap(medium.get('label', 'N/A')),
                self.to_bullets(self.add_tooltips(medium.get('summary', ''))),
                2
            ),
            self.expand_block(
                'Long-term (6-12 months)',
                long.get('label', 'N/A'),
                self.heatmap(long.get('label', 'N/A')),
                self.to_bullets(self.add_tooltips(long.get('summary', ''))),
                3
            )
        ]
        
        return f"<b>Time Horizon Recommendations:</b><br><br>{''.join(blocks)}"
    
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

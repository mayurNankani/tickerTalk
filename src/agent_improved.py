from typing import Dict, Any, Optional, Tuple
import math
from src.tools.fundamental_analysis import FundamentalAnalysis
from src.tools.technical_analysis import TechnicalAnalysis
from src.tools.company_search import CompanySearch
from src.tools.sentiment_analysis import SentimentAnalyzer
from src.tools.finnhub_news import FinnhubNewsAgent

# Sector-specific weight adjustments for fundamental metrics
SECTOR_WEIGHTS = {
    "Technology": {"growth": 1.5, "valuation": 0.7, "profitability": 1.3, "health": 0.8},
    "Financial": {"growth": 0.8, "valuation": 1.2, "profitability": 1.1, "health": 1.5},
    "Healthcare": {"growth": 1.3, "valuation": 0.9, "profitability": 1.0, "health": 1.2},
    "Consumer": {"growth": 1.0, "valuation": 1.0, "profitability": 1.2, "health": 1.0},
    "Energy": {"growth": 0.9, "valuation": 1.3, "profitability": 1.4, "health": 1.1},
    "Utilities": {"growth": 0.6, "valuation": 1.1, "profitability": 1.0, "health": 1.3},
    "default": {"growth": 1.0, "valuation": 1.0, "profitability": 1.0, "health": 1.0}
}

# One-line human-friendly tooltips used to build the summary returned with analysis
FUNDAMENTAL_TOOLTIPS = {
    "market_cap": "Company size measured as share price × shares outstanding; context for stability/risk.",
    "pe_ratio": "Price divided by last 12 months' earnings; lower often means cheaper relative to earnings.",
    "forward_pe": "Price divided by projected earnings; shows valuation based on expected profit.",
    "peg_ratio": "PE divided by earnings growth rate; adjusts valuation for growth (≈1 ≈ fair).",
    "price_to_book": "Price relative to book value per share; useful for asset-heavy businesses.",
    "price_to_sales": "Market value divided by revenue; handy for low-margin firms.",
    "enterprise_value": "Company value including debt and cash; used for capital-structure-neutral comparisons.",
    "enterprise_to_revenue": "EV divided by revenue; valuation vs sales.",
    "enterprise_to_ebitda": "EV divided by operating earnings; common cross-company valuation.",
    "revenue_growth": "Year-over-year top-line growth; indicates demand and expansion speed.",
    "earnings_growth": "Growth in net income; shows profit trend and scalability.",
    "earnings_quarterly_growth": "Recent quarterly earnings momentum versus prior periods.",
    "debt_to_equity": "Total debt ÷ shareholders' equity; higher means more leverage risk.",
    "current_ratio": "Current assets ÷ current liabilities; measures short-term liquidity.",
    "quick_ratio": "(Current assets − inventory) ÷ current liabilities; stricter liquidity check.",
    "total_cash": "Cash on the balance sheet; available liquidity and cushion.",
    "total_debt": "Sum of borrowings; indicates leverage exposure.",
    "profit_margins": "Net profit ÷ revenue; higher = more profit retained per sale.",
    "operating_margins": "Operating income ÷ revenue; shows operational efficiency.",
    "gross_margins": "Gross profit ÷ revenue; basic product/service margin.",
    "return_on_equity": "Net income ÷ shareholder equity; how well equity generates profit.",
    "return_on_assets": "Net income ÷ total assets; efficiency of asset use.",
    "dividend_yield": "Annual dividends ÷ share price; income return from holding the stock.",
    "payout_ratio": "Share of earnings paid as dividends; indicates dividend sustainability.",
    "dividend_rate": "Dollar dividend paid per share annually.",
    "inventory_turnover": "How often inventory is sold per period; higher usually means efficiency.",
    "asset_turnover": "Revenue ÷ total assets; measures how effectively assets generate sales."
}

TECHNICAL_TOOLTIPS = {
    "current_price": "The most recent closing price; immediate market value reference.",
    "price_change": "Percent change from previous close; shows short-term movement.",
    "rsi": "Relative Strength Index (0–100); <30 often oversold (buy), >70 overbought (sell).",
    "stoch_k": "Stochastic %K; compares close to recent high-low range (used with %D).",
    "stoch_d": "Stochastic %D; smoothed %K used for crossovers.",
    "ultimate_oscillator": "Momentum indicator using multiple timeframes to reduce false signals.",
    "macd": "MACD line (short EMA − long EMA); shows trend direction and momentum.",
    "macd_signal": "Smoothed MACD used for crossovers (trade signal line).",
    "macd_hist": "MACD − signal; rising positive histogram shows strengthening bullish momentum.",
    "adx": "Average Directional Index; measures trend strength (values > ~25 indicate a strong trend).",
    "adx_positive": "+DI (directional indicator); when > -DI indicates upward bias.",
    "adx_negative": "-DI (directional indicator); when > +DI indicates downward bias.",
    "bb_upper": "Bollinger upper band; price near bands signals extremes.",
    "bb_middle": "Bollinger middle (MA); center of the bands.",
    "bb_lower": "Bollinger lower band; price near bands signals extremes.",
    "bb_width": "Width of Bollinger Bands relative to MA; narrow = low volatility, wide = high volatility.",
    "atr": "Average True Range; average size of daily price moves (volatility measure).",
    "obv": "On-Balance Volume; cumulative volume trend used to confirm price moves.",
    "mfi": "Money Flow Index; volume-weighted momentum oscillator, extremes suggest overbought/oversold.",
    "sma_20": "20-period Simple Moving Average; price above suggests short-term uptrend.",
    "sma_50": "50-period Simple Moving Average; price above suggests medium-term uptrend.",
    "sma_200": "200-period Simple Moving Average; price above suggests long-term uptrend.",
    "ema_20": "20-period Exponential Moving Average; gives more weight to recent prices.",
    "above_sma_20": "Boolean: whether price is above the 20-period SMA (quick trend check).",
    "above_sma_50": "Boolean: whether price is above the 50-period SMA (quick trend check).",
    "above_sma_200": "Boolean: whether price is above the 200-period SMA (long-term trend check).",
    "sma_20_cross_50": "True when SMA20 crosses above SMA50 indicating a bullish trend change (golden cross).",
    "sma_50_cross_200": "True when SMA50 crosses above SMA200 indicating a major bullish trend change (golden cross)."
}

def _format_value(val: Any) -> str:
    try:
        if isinstance(val, float):
            return str(round(val, 4))
        return str(val)
    except Exception:
        return str(val)

class StockAnalysisAgentImproved:
    """Improved stock analysis with weighted scoring, sector adjustments, and confidence metrics"""
    
    def __init__(self):
        self.fundamental_analyzer = FundamentalAnalysis()
        self.technical_analyzer = TechnicalAnalysis()
        self.company_searcher = CompanySearch()
        self.sentiment_analyzer = SentimentAnalyzer()
        self.news_agent = FinnhubNewsAgent()

    def analyze_stock(self, ticker: str) -> Dict[str, Any]:
        """
        Analyze a stock using both fundamental and technical analysis.
        
        Args:
            ticker (str): The stock ticker symbol
            
        Returns:
            Dict[str, Any]: Combined analysis results
        """
        # Perform fundamental analysis
        fundamental_result_obj = self.fundamental_analyzer.analyze(ticker)
        
        # Extract data from ToolResult or use directly if dict
        if hasattr(fundamental_result_obj, 'data'):
            fundamental_results = fundamental_result_obj.data if fundamental_result_obj.data else {}
        else:
            fundamental_results = fundamental_result_obj

        # Perform technical analysis
        technical_result_obj = self.technical_analyzer.analyze(ticker)
        
        # Extract data from ToolResult or use directly if dict
        if hasattr(technical_result_obj, 'data'):
            technical_results = technical_result_obj.data if technical_result_obj.data else {}
        else:
            technical_results = technical_result_obj

        # Build human-readable fundamental summary
        fundamental_summary = []
        if isinstance(fundamental_results, dict) and not fundamental_results.get("error"):
            fkeys = [
                "market_cap", "pe_ratio", "peg_ratio", "revenue_growth", "earnings_growth",
                "debt_to_equity", "current_ratio", "profit_margins", "return_on_equity"
            ]
            for k in fkeys:
                v = fundamental_results.get(k)
                if v is not None:
                    fundamental_summary.append(f"{k}: {_format_value(v)} — {FUNDAMENTAL_TOOLTIPS.get(k, '')}")
        else:
            if isinstance(fundamental_results, dict) and fundamental_results.get("error"):
                fundamental_summary.append(f"error: {fundamental_results.get('error')}")

        technical_summary = []
        if isinstance(technical_results, dict) and not technical_results.get("error"):
            tkeys = [
                "current_price", "price_change", "rsi", "macd", "macd_signal", "macd_hist",
                "adx", "bb_width", "atr", "mfi", "sma_20", "sma_50", "sma_20_cross_50"
            ]
            for k in tkeys:
                v = technical_results.get(k)
                if v is not None:
                    technical_summary.append(f"{k}: {_format_value(v)} — {TECHNICAL_TOOLTIPS.get(k, '')}")
        else:
            if isinstance(technical_results, dict) and technical_results.get("error"):
                technical_summary.append(f"error: {technical_results.get('error')}")

        # Combine results
        analysis = {
            "ticker": ticker,
            "fundamental_analysis": fundamental_results,
            "technical_analysis": technical_results,
            "fundamental_summary": fundamental_summary,
            "technical_summary": technical_summary
        }

        return analysis

    def _get_sector_weights(self, fundamental_data: Dict[str, Any]) -> Dict[str, float]:
        """Get sector-specific weights, defaulting to standard weights"""
        # Could extract sector from fundamental_data if available
        # For now, use default weights
        return SECTOR_WEIGHTS["default"]

    def _reason_items(self, summary: str) -> list[str]:
        """Split component summary into individual reason items."""
        text = (summary or "").strip()
        if not text:
            return []
        return [item.strip() for item in text.split(",") if item.strip()]

    def _select_horizon_items(self, section: str, horizon: str, summary: str) -> str:
        """Pick the most relevant subset of reason items for the requested horizon."""
        items = self._reason_items(summary)
        if not items:
            return ""

        if section == "fundamental" and horizon == "medium":
            # Medium term should lean toward valuation + growth/execution.
            return ", ".join(items[:2])

        if section == "fundamental" and horizon == "long":
            # Long term should lean toward durability/quality first.
            quality_terms = (
                "debt", "liquidity", "margin", "roe", "book value", "current ratio"
            )
            quality_items = [item for item in items if any(term in item.lower() for term in quality_terms)]
            chosen = quality_items[:2] or items[-2:]
            return ", ".join(chosen)

        if section == "technical" and horizon == "medium":
            # Medium term should favor actionable momentum/trend confirmation.
            medium_terms = ("macd", "rsi", "adx", "sma20", "sma50", "stochastic", "mfi")
            medium_items = [item for item in items if any(term in item.lower() for term in medium_terms)]
            chosen = medium_items[:2] or items[:2]
            return ", ".join(chosen)

        if section == "technical" and horizon == "long":
            # Long term should favor structural trend markers.
            long_terms = ("sma200", "golden cross", "major golden cross", "long-term uptrend", "long-term downtrend")
            long_items = [item for item in items if any(term in item.lower() for term in long_terms)]
            return ", ".join(long_items[:2])

        if section == "sentiment" and horizon == "medium":
            return ", ".join(items[:1])

        return ", ".join(items)

    def _horizon_reason(self, section: str, horizon: str, summary: str) -> str:
        """Wrap component summaries with horizon-specific framing so each horizon reads differently."""
        text = self._select_horizon_items(section, horizon, summary)
        if not text:
            return ""

        if section == "technical" and horizon == "short":
            return f"Near-term momentum setup: {text}"
        if section == "sentiment" and horizon == "short":
            return f"News-driven catalyst bias (1-4 weeks): {text}"

        if section == "fundamental" and horizon == "medium":
            return f"Fundamental setup for the next quarter: {text}"
        if section == "technical" and horizon == "medium":
            return f"Trend confirmation over the next few months: {text}"
        if section == "sentiment" and horizon == "medium":
            return f"Sentiment tailwind/headwind for medium term: {text}"

        if section == "fundamental" and horizon == "long":
            return f"Long-horizon business quality and valuation: {text}"
        if section == "technical" and horizon == "long":
            return f"Primary trend structure for 6-12 months: {text}"

        return text

    def get_fundamental_recommendation(self, fundamental_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate recommendation based on fundamental analysis using weighted, continuous scoring.
        
        Returns a dict with: 'label', 'summary', 'score' (0-100), 'confidence' (0-100)
        """
        try:
            total_score = 0
            max_possible_score = 0
            reasons = []
            weights = self._get_sector_weights(fundamental_data)
            
            # ===== VALUATION METRICS =====
            valuation_score = 0
            valuation_max = 0
            
            # P/E Ratio - Continuous scoring with diminishing returns
            if fundamental_data.get('pe_ratio') and fundamental_data['pe_ratio'] > 0:
                pe = fundamental_data['pe_ratio']
                # Optimal PE around 15, score decreases as we move away
                if pe < 10:
                    pe_score = 0.7  # Cheap, slightly concerning but not terrible
                elif pe < 15:
                    pe_score = 1.0  # Sweet spot
                elif pe < 25:
                    pe_score = 0.75 - (pe - 15) * 0.015  # Gradually decrease (more generous)
                elif pe < 40:
                    pe_score = 0.5 - (pe - 25) * 0.01  # Less harsh penalty
                else:
                    pe_score = max(0, 0.35 - (pe - 40) * 0.01)  # More lenient for very high PE
                
                valuation_score += pe_score * 3.0  # Weight of 3
                valuation_max += 3.0
                if pe_score >= 0.8:
                    reasons.append(f"Attractive P/E ({_format_value(pe)})")
                elif pe_score <= 0.3:
                    reasons.append(f"High P/E ({_format_value(pe)})")
            
            # PEG Ratio - Growth-adjusted valuation
            if fundamental_data.get('peg_ratio') and fundamental_data['peg_ratio'] > 0:
                peg = fundamental_data['peg_ratio']
                if peg < 0.5:
                    peg_score = 1.0
                elif peg < 1.0:
                    peg_score = 0.95 - (peg - 0.5) * 0.3  # More generous
                elif peg < 2.0:
                    peg_score = 0.7 - (peg - 1.0) * 0.25  # More generous
                elif peg < 3.0:
                    peg_score = 0.45 - (peg - 2.0) * 0.15  # New tier
                else:
                    peg_score = max(0, 0.3 - (peg - 3.0) * 0.1)
                
                valuation_score += peg_score * 4.0  # Weight of 4 (very important)
                valuation_max += 4.0
                if peg_score >= 0.8:
                    reasons.append(f"Excellent PEG ({_format_value(peg)})")
            
            # Price-to-Book
            if fundamental_data.get('price_to_book') and fundamental_data['price_to_book'] > 0:
                pb = fundamental_data['price_to_book']
                if pb < 1:
                    pb_score = 0.9
                elif pb < 3:
                    pb_score = 0.8 - (pb - 1) * 0.15
                elif pb < 5:
                    pb_score = 0.5 - (pb - 3) * 0.1
                else:
                    pb_score = max(0, 0.3 - (pb - 5) * 0.05)
                
                valuation_score += pb_score * 2.0
                valuation_max += 2.0
                if pb_score >= 0.8:
                    reasons.append(f"Near/below book value (P/B: {_format_value(pb)})")
            
            # Apply sector weight to valuation
            if valuation_max > 0:
                weighted_valuation = (valuation_score / valuation_max) * 10 * weights["valuation"]
                total_score += weighted_valuation
                max_possible_score += 10 * weights["valuation"]
            
            # ===== GROWTH METRICS =====
            growth_score = 0
            growth_max = 0
            
            # Revenue Growth - Continuous scoring
            if fundamental_data.get('revenue_growth') is not None:
                rev_growth = fundamental_data['revenue_growth']
                rev_pct = rev_growth * 100
                
                if rev_pct > 30:
                    rev_score = 1.0
                elif rev_pct > 20:
                    rev_score = 0.85 + (rev_pct - 20) * 0.015
                elif rev_pct > 10:
                    rev_score = 0.65 + (rev_pct - 10) * 0.02
                elif rev_pct > 5:
                    rev_score = 0.5 + (rev_pct - 5) * 0.03
                elif rev_pct > 0:
                    rev_score = 0.4 + rev_pct * 0.02
                else:
                    rev_score = max(0, 0.4 + rev_pct * 0.05)  # Penalize negative
                
                growth_score += rev_score * 4.0
                growth_max += 4.0
                if rev_score >= 0.8:
                    reasons.append(f"Strong revenue growth ({_format_value(rev_growth)})")
                elif rev_score <= 0.3:
                    reasons.append(f"Declining revenue ({_format_value(rev_growth)})")
            
            # Earnings Growth
            if fundamental_data.get('earnings_growth') is not None:
                earn_growth = fundamental_data['earnings_growth']
                earn_pct = earn_growth * 100
                
                if earn_pct > 30:
                    earn_score = 1.0
                elif earn_pct > 20:
                    earn_score = 0.85 + (earn_pct - 20) * 0.015
                elif earn_pct > 10:
                    earn_score = 0.65 + (earn_pct - 10) * 0.02
                elif earn_pct > 5:
                    earn_score = 0.5 + (earn_pct - 5) * 0.03
                elif earn_pct > 0:
                    earn_score = 0.4 + earn_pct * 0.02
                else:
                    earn_score = max(0, 0.4 + earn_pct * 0.05)
                
                growth_score += earn_score * 5.0  # Most important growth metric
                growth_max += 5.0
                if earn_score >= 0.8:
                    reasons.append(f"High earnings growth ({_format_value(earn_growth)})")
                elif earn_score <= 0.3:
                    reasons.append(f"Negative earnings growth ({_format_value(earn_growth)})")
            
            # Apply sector weight to growth
            if growth_max > 0:
                weighted_growth = (growth_score / growth_max) * 10 * weights["growth"]
                total_score += weighted_growth
                max_possible_score += 10 * weights["growth"]
            
            # ===== FINANCIAL HEALTH METRICS =====
            health_score = 0
            health_max = 0
            
            # Debt-to-Equity
            if fundamental_data.get('debt_to_equity') is not None:
                de = fundamental_data['debt_to_equity']
                if de < 0.3:
                    de_score = 1.0
                elif de < 0.5:
                    de_score = 0.95
                elif de < 1.0:
                    de_score = 0.85 - (de - 0.5) * 0.15  # More generous
                elif de < 1.5:
                    de_score = 0.7 - (de - 1.0) * 0.2  # More generous
                elif de < 2.0:
                    de_score = 0.6 - (de - 1.5) * 0.15  # More generous
                elif de < 3.0:
                    de_score = 0.45 - (de - 2.0) * 0.1  # New tier - less harsh
                else:
                    de_score = max(0, 0.35 - (de - 3.0) * 0.1)
                
                health_score += de_score * 3.5
                health_max += 3.5
                if de_score >= 0.85:
                    reasons.append(f"Low debt-to-equity ({_format_value(de)})")
                elif de_score <= 0.4:
                    reasons.append(f"High debt-to-equity ({_format_value(de)})")
            
            # Current Ratio - Liquidity
            if fundamental_data.get('current_ratio'):
                cr = fundamental_data['current_ratio']
                if cr > 2.5:
                    cr_score = 1.0
                elif cr > 2.0:
                    cr_score = 0.9
                elif cr > 1.5:
                    cr_score = 0.75
                elif cr > 1.2:
                    cr_score = 0.6
                elif cr > 1.0:
                    cr_score = 0.45
                else:
                    cr_score = max(0, 0.3 - (1.0 - cr) * 0.4)
                
                health_score += cr_score * 2.5
                health_max += 2.5
                if cr_score >= 0.85:
                    reasons.append(f"Strong liquidity (CR: {_format_value(cr)})")
                elif cr_score <= 0.4:
                    reasons.append(f"Liquidity concerns (CR: {_format_value(cr)})")
            
            # Quick Ratio (if available)
            if fundamental_data.get('quick_ratio'):
                qr = fundamental_data['quick_ratio']
                if qr > 1.5:
                    qr_score = 1.0
                elif qr > 1.0:
                    qr_score = 0.8 + (qr - 1.0) * 0.4
                elif qr > 0.8:
                    qr_score = 0.6 + (qr - 0.8) * 1.0
                else:
                    qr_score = qr * 0.75
                
                health_score += qr_score * 2.0
                health_max += 2.0
            
            # Apply sector weight
            if health_max > 0:
                weighted_health = (health_score / health_max) * 10 * weights["health"]
                total_score += weighted_health
                max_possible_score += 10 * weights["health"]
            
            # ===== PROFITABILITY METRICS =====
            profit_score = 0
            profit_max = 0
            
            # Profit Margins
            if fundamental_data.get('profit_margins') is not None:
                pm = fundamental_data['profit_margins']
                pm_pct = pm * 100
                
                if pm_pct > 25:
                    pm_score = 1.0
                elif pm_pct > 20:
                    pm_score = 0.9 + (pm_pct - 20) * 0.02
                elif pm_pct > 15:
                    pm_score = 0.75 + (pm_pct - 15) * 0.03
                elif pm_pct > 10:
                    pm_score = 0.6 + (pm_pct - 10) * 0.03
                elif pm_pct > 5:
                    pm_score = 0.45 + (pm_pct - 5) * 0.03
                elif pm_pct > 0:
                    pm_score = 0.3 + pm_pct * 0.03
                else:
                    pm_score = max(0, 0.3 + pm_pct * 0.1)
                
                profit_score += pm_score * 4.0
                profit_max += 4.0
                if pm_score >= 0.85:
                    reasons.append(f"Excellent margins ({_format_value(pm)})")
                elif pm_score <= 0.3:
                    reasons.append(f"Low/negative margins ({_format_value(pm)})")
            
            # Return on Equity
            if fundamental_data.get('return_on_equity') is not None:
                roe = fundamental_data['return_on_equity']
                roe_pct = roe * 100
                
                if roe_pct > 25:
                    roe_score = 1.0
                elif roe_pct > 20:
                    roe_score = 0.9 + (roe_pct - 20) * 0.02
                elif roe_pct > 15:
                    roe_score = 0.75 + (roe_pct - 15) * 0.03
                elif roe_pct > 10:
                    roe_score = 0.6 + (roe_pct - 10) * 0.03
                elif roe_pct > 5:
                    roe_score = 0.45 + (roe_pct - 5) * 0.03
                elif roe_pct > 0:
                    roe_score = 0.3 + roe_pct * 0.03
                else:
                    roe_score = max(0, 0.3 + roe_pct * 0.05)
                
                profit_score += roe_score * 4.5
                profit_max += 4.5
                if roe_score >= 0.85:
                    reasons.append(f"High ROE ({_format_value(roe)})")
                elif roe_score <= 0.3:
                    reasons.append(f"Poor ROE ({_format_value(roe)})")
            
            # Operating Margins (if available)
            if fundamental_data.get('operating_margins'):
                om = fundamental_data['operating_margins']
                om_pct = om * 100
                
                if om_pct > 20:
                    om_score = 1.0
                elif om_pct > 15:
                    om_score = 0.85 + (om_pct - 15) * 0.03
                elif om_pct > 10:
                    om_score = 0.65 + (om_pct - 10) * 0.04
                elif om_pct > 5:
                    om_score = 0.45 + (om_pct - 5) * 0.04
                else:
                    om_score = max(0, 0.45 + om_pct * 0.05)
                
                profit_score += om_score * 2.5
                profit_max += 2.5
            
            # Apply sector weight
            if profit_max > 0:
                weighted_profit = (profit_score / profit_max) * 10 * weights["profitability"]
                total_score += weighted_profit
                max_possible_score += 10 * weights["profitability"]
            
            # ===== CALCULATE FINAL SCORE AND CONFIDENCE =====
            if max_possible_score > 0:
                normalized_score = (total_score / max_possible_score) * 100
            else:
                normalized_score = 50  # Neutral if no data
            
            # Calculate confidence based on data availability
            metrics_available = sum([
                1 if fundamental_data.get('pe_ratio') else 0,
                1 if fundamental_data.get('peg_ratio') else 0,
                1 if fundamental_data.get('revenue_growth') is not None else 0,
                1 if fundamental_data.get('earnings_growth') is not None else 0,
                1 if fundamental_data.get('debt_to_equity') is not None else 0,
                1 if fundamental_data.get('current_ratio') else 0,
                1 if fundamental_data.get('profit_margins') is not None else 0,
                1 if fundamental_data.get('return_on_equity') is not None else 0,
            ])
            confidence = min(100, (metrics_available / 8) * 100)
            
            # Map normalized score to label - adjusted for more decisive recommendations
            if normalized_score >= 70:
                label = "STRONG BUY"
            elif normalized_score >= 55:
                label = "BUY"
            elif normalized_score >= 45:
                label = "HOLD"
            elif normalized_score >= 30:
                label = "SELL"
            else:
                label = "STRONG SELL"

            # Build summary
            if reasons:
                summary = ", ".join(reasons)
            else:
                summary = "No strong fundamental signals detected."

            return {
                "label": label,
                "summary": summary,
                "score": round(normalized_score, 1),
                "confidence": round(confidence, 1)
            }
                
        except Exception as e:
            print(f"Error in fundamental recommendation: {e}")
            return {"label": "HOLD", "summary": "Error computing fundamental recommendation.", "score": 50, "confidence": 0}

    def get_technical_recommendation(self, technical_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate recommendation based on technical analysis using weighted scoring.
        
        Returns a dict with: 'label', 'summary', 'score' (0-100), 'confidence' (0-100)
        """
        try:
            total_score = 0
            max_possible_score = 0
            reasons = []
            
            # ===== MOMENTUM INDICATORS =====
            
            # RSI - Weighted by strength of signal
            if technical_data.get('rsi'):
                rsi = technical_data['rsi']
                # Calculate distance from extremes (30 and 70)
                if rsi < 30:  # Oversold
                    rsi_score = 1.0 - (rsi / 30) * 0.3  # More oversold = higher score
                    total_score += rsi_score * 5.0
                    reasons.append(f"RSI oversold ({_format_value(rsi)})")
                elif rsi < 40:
                    rsi_score = 0.6 + (40 - rsi) * 0.02
                    total_score += rsi_score * 5.0
                elif rsi > 70:  # Overbought
                    rsi_score = max(0, 0.3 - (rsi - 70) * 0.02)
                    total_score += rsi_score * 5.0
                    reasons.append(f"RSI overbought ({_format_value(rsi)})")
                elif rsi > 60:
                    rsi_score = 0.6 - (rsi - 60) * 0.02
                    total_score += rsi_score * 5.0
                else:  # Neutral zone 40-60
                    rsi_score = 0.5
                    total_score += rsi_score * 5.0
                
                max_possible_score += 5.0
            
            # Stochastic - More nuanced crossover analysis
            if technical_data.get('stoch_k') and technical_data.get('stoch_d'):
                stoch_k = technical_data['stoch_k']
                stoch_d = technical_data['stoch_d']
                
                # Level scoring
                if stoch_k < 20 and stoch_d < 20:
                    level_score = 1.0
                    reasons.append(f"Stochastic oversold (K={_format_value(stoch_k)})")
                elif stoch_k > 80 and stoch_d > 80:
                    level_score = 0.0
                    reasons.append(f"Stochastic overbought (K={_format_value(stoch_k)})")
                else:
                    level_score = 0.5
                
                # Crossover scoring
                cross_diff = stoch_k - stoch_d
                if cross_diff > 5:  # Strong bullish
                    cross_score = 0.8
                elif cross_diff > 0:  # Mild bullish
                    cross_score = 0.6
                elif cross_diff > -5:  # Mild bearish
                    cross_score = 0.4
                else:  # Strong bearish
                    cross_score = 0.2
                
                stoch_combined = (level_score * 0.6 + cross_score * 0.4)
                total_score += stoch_combined * 4.0
                max_possible_score += 4.0
            
            # MFI (Money Flow Index)
            if technical_data.get('mfi'):
                mfi = technical_data['mfi']
                if mfi < 20:
                    mfi_score = 1.0
                    total_score += mfi_score * 4.0
                    reasons.append(f"MFI oversold ({_format_value(mfi)})")
                elif mfi < 30:
                    mfi_score = 0.7 + (30 - mfi) * 0.03
                    total_score += mfi_score * 4.0
                elif mfi > 80:
                    mfi_score = 0.0
                    total_score += mfi_score * 4.0
                    reasons.append(f"MFI overbought ({_format_value(mfi)})")
                elif mfi > 70:
                    mfi_score = 0.3 - (mfi - 70) * 0.03
                    total_score += mfi_score * 4.0
                else:
                    mfi_score = 0.5
                    total_score += mfi_score * 4.0
                
                max_possible_score += 4.0
            
            # ===== TREND INDICATORS =====
            
            # MACD - Histogram strength matters
            if all(key in technical_data for key in ['macd', 'macd_signal', 'macd_hist']):
                macd_hist = technical_data['macd_hist']
                
                if macd_hist > 0:
                    # Bullish - stronger histogram = better score
                    macd_score = 0.6 + min(0.4, abs(macd_hist) * 0.1)
                    if technical_data['macd'] > technical_data['macd_signal']:
                        reasons.append("MACD bullish crossover")
                else:
                    # Bearish
                    macd_score = 0.4 - min(0.4, abs(macd_hist) * 0.1)
                    if technical_data['macd'] < technical_data['macd_signal']:
                        reasons.append("MACD bearish crossover")
                
                total_score += macd_score * 5.0
                max_possible_score += 5.0
            
            # ADX - Trend strength
            if technical_data.get('adx'):
                adx = technical_data['adx']
                adx_pos = technical_data.get('adx_positive', 0)
                adx_neg = technical_data.get('adx_negative', 0)
                
                # Only strong trends matter (ADX > 25)
                if adx > 25:
                    if adx_pos > adx_neg:
                        # Strong uptrend
                        trend_strength = min(1.0, (adx - 25) / 25)
                        adx_score = 0.6 + trend_strength * 0.4
                        reasons.append(f"Strong uptrend (ADX={_format_value(adx)})")
                    else:
                        # Strong downtrend
                        trend_strength = min(1.0, (adx - 25) / 25)
                        adx_score = 0.4 - trend_strength * 0.4
                        reasons.append(f"Strong downtrend (ADX={_format_value(adx)})")
                else:
                    adx_score = 0.5  # Weak trend, neutral
                
                total_score += adx_score * 4.5
                max_possible_score += 4.5
            
            # Moving Averages - Position and crossovers
            ma_score = 0
            ma_weight = 0
            
            if technical_data.get('above_sma_20') is not None:
                if technical_data['above_sma_20']:
                    ma_score += 0.7 * 2.0
                    reasons.append("Price above SMA20")
                else:
                    ma_score += 0.3 * 2.0
                    reasons.append("Price below SMA20")
                ma_weight += 2.0
            
            if technical_data.get('above_sma_50') is not None:
                if technical_data['above_sma_50']:
                    ma_score += 0.75 * 2.5
                    reasons.append("Price above SMA50")
                else:
                    ma_score += 0.25 * 2.5
                    reasons.append("Price below SMA50")
                ma_weight += 2.5
            
            # SMA 200 - Long-term trend (important for all timeframes)
            if technical_data.get('above_sma_200') is not None:
                if technical_data['above_sma_200']:
                    ma_score += 0.8 * 3.0  # Strong signal
                    reasons.append("Price above SMA200 (long-term uptrend)")
                else:
                    ma_score += 0.2 * 3.0
                    reasons.append("Price below SMA200 (long-term downtrend)")
                ma_weight += 3.0
            
            if technical_data.get('sma_20_cross_50'):  # Golden Cross
                ma_score += 1.0 * 3.0
                reasons.append("Golden cross (SMA20 > SMA50)")
                ma_weight += 3.0
            
            if technical_data.get('sma_50_cross_200'):  # Major Golden Cross
                ma_score += 1.0 * 4.0
                reasons.append("Major golden cross (SMA50 > SMA200)")
                ma_weight += 4.0
            
            if ma_weight > 0:
                total_score += ma_score
                max_possible_score += ma_weight
            
            # ===== VOLATILITY INDICATORS =====
            
            # Bollinger Bands
            if all(key in technical_data for key in ['current_price', 'bb_upper', 'bb_lower', 'bb_width']):
                price = technical_data['current_price']
                bb_upper = technical_data['bb_upper']
                bb_lower = technical_data['bb_lower']
                bb_width = technical_data['bb_width']
                bb_middle = (bb_upper + bb_lower) / 2
                
                # Position within bands
                if price < bb_lower:
                    bb_position_score = 1.0  # Oversold
                    reasons.append("Price below lower Bollinger Band")
                elif price > bb_upper:
                    bb_position_score = 0.0  # Overbought
                    reasons.append("Price above upper Bollinger Band")
                else:
                    # Normalize position within bands
                    band_range = bb_upper - bb_lower
                    if band_range > 0:
                        position = (price - bb_lower) / band_range
                        bb_position_score = 1.0 - position  # Lower in band = higher score
                    else:
                        bb_position_score = 0.5
                
                # Volatility adjustment - high volatility reduces confidence
                if bb_width > 0.2:  # High volatility
                    volatility_factor = 0.7
                elif bb_width > 0.1:
                    volatility_factor = 0.85
                else:
                    volatility_factor = 1.0
                
                total_score += bb_position_score * 3.5 * volatility_factor
                max_possible_score += 3.5
            
            # ===== CALCULATE FINAL SCORE =====
            if max_possible_score > 0:
                normalized_score = (total_score / max_possible_score) * 100
            else:
                normalized_score = 50
            
            # Calculate confidence
            indicators_available = sum([
                1 if technical_data.get('rsi') else 0,
                1 if technical_data.get('stoch_k') else 0,
                1 if technical_data.get('mfi') else 0,
                1 if technical_data.get('macd') else 0,
                1 if technical_data.get('adx') else 0,
                1 if technical_data.get('above_sma_20') is not None else 0,
                1 if technical_data.get('above_sma_50') is not None else 0,
                1 if technical_data.get('above_sma_200') is not None else 0,
                1 if technical_data.get('bb_lower') else 0,
            ])
            confidence = min(100, (indicators_available / 9) * 100)
            
            # Map to label - adjusted for more decisive recommendations
            if normalized_score >= 70:
                label = "STRONG BUY"
            elif normalized_score >= 55:
                label = "BUY"
            elif normalized_score >= 45:
                label = "HOLD"
            elif normalized_score >= 30:
                label = "SELL"
            else:
                label = "STRONG SELL"

            # Build summary
            if reasons:
                summary = ", ".join(reasons)
            else:
                summary = "No strong technical signals detected."

            return {
                "label": label,
                "summary": summary,
                "score": round(normalized_score, 1),
                "confidence": round(confidence, 1)
            }
                
        except Exception as e:
            return {
                "label": "HOLD",
                "summary": f"Technical analysis error: {str(e)}",
                "score": 50,
                "confidence": 0
            }
    
    def _get_sentiment_recommendation(self, ticker: str) -> Dict[str, Any]:
        """
        Get news sentiment recommendation.
        
        Args:
            ticker: Stock ticker symbol
            
        Returns:
            Dict with sentiment score (0-100), label, summary, and confidence
        """
        try:
            # Check if sentiment analyzer is available
            if not self.sentiment_analyzer.is_available():
                return {
                    "label": "NEUTRAL",
                    "summary": "Sentiment analysis unavailable (model not loaded)",
                    "score": 50,
                    "confidence": 0
                }
            
            # Fetch news articles
            news_result = self.news_agent.fetch(ticker, max_items=5, days_back=7)

            # Preserve concrete adapter errors so users can diagnose configuration issues.
            news_error = (getattr(news_result, 'error', '') or '').strip() if news_result else ''
            if news_error:
                if 'api key' in news_error.lower() or 'finnhub' in news_error.lower():
                    return {
                        "label": "NEUTRAL",
                        "summary": "Sentiment unavailable (Finnhub API key not configured)",
                        "score": 50,
                        "confidence": 0
                    }
                return {
                    "label": "NEUTRAL",
                    "summary": f"Sentiment unavailable ({news_error})",
                    "score": 50,
                    "confidence": 0
                }
            
            # Check if news fetch was successful
            if not news_result or not news_result.data or not news_result.data.get('news'):
                return {
                    "label": "NEUTRAL",
                    "summary": "No recent news available",
                    "score": 50,
                    "confidence": 0
                }
            
            articles = news_result.data['news']
            
            # Analyze sentiment
            sentiment_result = self.sentiment_analyzer.analyze_news_articles(articles)
            
            overall_score = sentiment_result['overall_score']
            overall_sentiment = sentiment_result['overall_sentiment']
            confidence = sentiment_result['confidence']
            article_count = sentiment_result['article_count']
            
            # Determine label based on score
            if overall_score >= 60:
                label = "POSITIVE"
            elif overall_score <= 40:
                label = "NEGATIVE"
            else:
                label = "NEUTRAL"
            
            # Build summary - use semicolons or brackets to avoid comma splitting in UI
            sentiment_counts = []
            if sentiment_result['positive_count'] > 0:
                sentiment_counts.append(f"{sentiment_result['positive_count']} positive")
            if sentiment_result['negative_count'] > 0:
                sentiment_counts.append(f"{sentiment_result['negative_count']} negative")
            if sentiment_result['neutral_count'] > 0:
                sentiment_counts.append(f"{sentiment_result['neutral_count']} neutral")
            
            # Use brackets and semicolons to avoid being split by comma-based bullet parser
            summary = f"{overall_sentiment.capitalize()} news ({'; '.join(sentiment_counts)}; {article_count} articles)"
            
            return {
                "label": label,
                "summary": summary,
                "score": round(overall_score, 1),
                "confidence": round(confidence, 1),
                "article_count": article_count
            }
            
        except Exception as e:
            print(f"Error in technical recommendation: {e}")
            return {"label": "HOLD", "summary": "Error computing technical recommendation.", "score": 50, "confidence": 0}

    def get_recommendation(self, ticker: str) -> Dict[str, Any]:
        """
        Get comprehensive buy/sell/hold recommendations with confidence scores.
        
        Args:
            ticker (str): The stock ticker symbol
            
        Returns:
            Dict with short_term, medium_term, long_term recommendations plus scores
        """
        analysis = self.analyze_stock(ticker)
        fundamental_rec = self.get_fundamental_recommendation(analysis["fundamental_analysis"])
        technical_rec = self.get_technical_recommendation(analysis["technical_analysis"])
        
        # Get sentiment analysis from news
        sentiment_rec = self._get_sentiment_recommendation(ticker)
        sentiment_score = sentiment_rec.get('score', 50)
        sentiment_confidence = sentiment_rec.get('confidence', 0)

        # Short-term (1 week): 80% Technical, 20% Sentiment (momentum + news)
        t_score = technical_rec.get('score', 50)
        short_score = (t_score * 0.8) + (sentiment_score * 0.2)
        short_confidence = (technical_rec.get('confidence', 0) * 0.8 + sentiment_confidence * 0.2)
        
        if short_score >= 70:
            short_label = "STRONG BUY"
        elif short_score >= 55:
            short_label = "BUY"
        elif short_score >= 45:
            short_label = "HOLD"
        elif short_score >= 30:
            short_label = "SELL"
        else:
            short_label = "STRONG SELL"
        
        short_summary_parts = []
        short_tech = self._horizon_reason("technical", "short", technical_rec.get('summary', ''))
        short_sent = self._horizon_reason("sentiment", "short", sentiment_rec.get('summary', ''))
        if short_tech:
            short_summary_parts.append(f"Technical: {short_tech}")
        if short_sent:
            short_summary_parts.append(f"Sentiment: {short_sent}")
        
        short_term = {
            "label": short_label,
            "summary": " | ".join(short_summary_parts) if short_summary_parts else technical_rec.get('summary', ''),
            "score": round(short_score, 1),
            "confidence": round(short_confidence, 1)
        }

        # Medium-term (3 months): 55% Fundamental, 35% Technical, 10% Sentiment
        f_score = fundamental_rec.get('score', 50)
        medium_score = (f_score * 0.55) + (t_score * 0.35) + (sentiment_score * 0.10)
        medium_confidence = (fundamental_rec.get('confidence', 0) * 0.55 + technical_rec.get('confidence', 0) * 0.35 + sentiment_confidence * 0.10)
        
        if medium_score >= 70:
            medium_label = "STRONG BUY"
        elif medium_score >= 55:
            medium_label = "BUY"
        elif medium_score >= 45:
            medium_label = "HOLD"
        elif medium_score >= 30:
            medium_label = "SELL"
        else:
            medium_label = "STRONG SELL"
        
        medium_summary_parts = []
        medium_fund = self._horizon_reason("fundamental", "medium", fundamental_rec.get('summary', ''))
        medium_tech = self._horizon_reason("technical", "medium", technical_rec.get('summary', ''))
        medium_sent = self._horizon_reason("sentiment", "medium", sentiment_rec.get('summary', ''))
        if medium_fund:
            medium_summary_parts.append(f"Fundamentals: {medium_fund}")
        if medium_tech:
            medium_summary_parts.append(f"Technical: {medium_tech}")
        if medium_sent:
            medium_summary_parts.append(f"Sentiment: {medium_sent}")
        
        medium_term = {
            "label": medium_label,
            "summary": " | ".join(medium_summary_parts) if medium_summary_parts else "No combined rationale available.",
            "score": round(medium_score, 1),
            "confidence": round(medium_confidence, 1)
        }

        # Long-term (6-12 months): 80% Fundamental, 20% Technical (no sentiment)
        # Long-term is driven by fundamentals and long-term technical trends
        long_score = (f_score * 0.8) + (t_score * 0.2)
        long_confidence = (fundamental_rec.get('confidence', 0) * 0.8 + technical_rec.get('confidence', 0) * 0.2)
        
        if long_score >= 70:
            long_label = "STRONG BUY"
        elif long_score >= 55:
            long_label = "BUY"
        elif long_score >= 45:
            long_label = "HOLD"
        elif long_score >= 30:
            long_label = "SELL"
        else:
            long_label = "STRONG SELL"
        
        long_summary_parts = []
        long_fund = self._horizon_reason("fundamental", "long", fundamental_rec.get('summary', ''))
        long_tech = self._horizon_reason("technical", "long", technical_rec.get('summary', ''))
        if long_fund:
            long_summary_parts.append(f"Fundamentals: {long_fund}")
        # Include key technical trend indicators for long-term
        if long_tech:
            long_summary_parts.append(f"Technical: {long_tech}")
        
        long_term = {
            "label": long_label,
            "summary": " | ".join(long_summary_parts) if long_summary_parts else fundamental_rec.get('summary', ''),
            "score": round(long_score, 1),
            "confidence": round(long_confidence, 1)
        }

        return {
            "short_term": short_term,
            "medium_term": medium_term,
            "long_term": long_term,
            "fundamental": fundamental_rec,
            "technical": technical_rec,
            "sentiment": sentiment_rec
        }

    # Keep the existing search methods
    def find_ticker(self, company_name: str) -> Dict[str, Any]:
        """Search for a company's ticker symbol by name."""
        result_obj = self.company_searcher.analyze(company_name)
        
        if hasattr(result_obj, 'data'):
            return result_obj.data if result_obj.data else {'matches': [], 'count': 0}
        else:
            return result_obj

    def get_best_ticker_match(self, company_name: str) -> Optional[str]:
        """Get the most likely ticker symbol for a company name."""
        matches = self.find_ticker(company_name)
        
        if matches and isinstance(matches, dict):
            match_list = matches.get('matches', [])
            if match_list and len(match_list) > 0:
                return match_list[0].get('symbol')
        
        return None

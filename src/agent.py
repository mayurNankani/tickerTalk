from typing import Dict, Any, Optional
from src.tools.fundamental_analysis import FundamentalAnalysis
from src.tools.technical_analysis import TechnicalAnalysis
from src.tools.company_search import CompanySearch

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
    "ema_20": "20-period Exponential Moving Average; gives more weight to recent prices.",
    "above_sma_20": "Boolean: whether price is above the 20-period SMA (quick trend check).",
    "above_sma_50": "Boolean: whether price is above the 50-period SMA (quick trend check).",
    "sma_20_cross_50": "True when SMA20 crosses above SMA50 indicating a bullish trend change (golden cross)."
}

def _format_value(val: Any) -> str:
    try:
        if isinstance(val, float):
            return str(round(val, 4))
        return str(val)
    except Exception:
        return str(val)

class StockAnalysisAgent:
    def __init__(self):
        self.fundamental_analyzer = FundamentalAnalysis()
        self.technical_analyzer = TechnicalAnalysis()
        self.company_searcher = CompanySearch()

    def analyze_stock(self, ticker: str) -> Dict[str, Any]:
        """
        Analyze a stock using both fundamental and technical analysis.
        
        Args:
            ticker (str): The stock ticker symbol
            
        Returns:
            Dict[str, Any]: Combined analysis results
        """
        # Perform fundamental analysis
        fundamental_results = self.fundamental_analyzer.analyze(ticker)

        # Perform technical analysis
        technical_results = self.technical_analyzer.analyze(ticker)

        # Build human-friendly summaries using the tooltip mappings
        fundamental_summary = []
        if isinstance(fundamental_results, dict) and not fundamental_results.get("error"):
            # choose a subset of keys to show in summary (order matters)
            keys = [
                "market_cap", "pe_ratio", "forward_pe", "peg_ratio", "price_to_book",
                "revenue_growth", "earnings_growth", "profit_margins", "return_on_equity",
                "debt_to_equity", "current_ratio", "dividend_yield"
            ]
            for k in keys:
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

    def get_fundamental_recommendation(self, fundamental_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate recommendation based on fundamental analysis.

        Returns a dict with keys: 'label' and 'summary' (short rationale).
        """
        try:
            score = 0
            reasons = []
            
            # Valuation Metrics
            if fundamental_data.get('pe_ratio'):
                if fundamental_data['pe_ratio'] < 15:
                    score += 2
                    reasons.append(f"Low PE ({_format_value(fundamental_data['pe_ratio'])})")
                elif fundamental_data['pe_ratio'] < 25:
                    score += 1
                    reasons.append(f"Moderate PE ({_format_value(fundamental_data['pe_ratio'])})")
                elif fundamental_data['pe_ratio'] > 35:
                    score -= 1
                    reasons.append(f"High PE ({_format_value(fundamental_data['pe_ratio'])})")
                    
            if fundamental_data.get('peg_ratio'):
                if 0 < fundamental_data['peg_ratio'] < 1:
                    score += 2
                    reasons.append(f"Low PEG ({_format_value(fundamental_data['peg_ratio'])})")
                elif 1 <= fundamental_data['peg_ratio'] < 2:
                    score += 1
                    reasons.append(f"Reasonable PEG ({_format_value(fundamental_data['peg_ratio'])})")
                elif fundamental_data['peg_ratio'] > 3:
                    score -= 1
                    reasons.append(f"High PEG ({_format_value(fundamental_data['peg_ratio'])})")
                    
            if fundamental_data.get('price_to_book'):
                if fundamental_data['price_to_book'] < 1:
                    score += 2
                    reasons.append(f"Low P/B ({_format_value(fundamental_data['price_to_book'])})")
                elif fundamental_data['price_to_book'] < 3:
                    score += 1
                    reasons.append(f"Moderate P/B ({_format_value(fundamental_data['price_to_book'])})")
                elif fundamental_data['price_to_book'] > 5:
                    score -= 1
                    reasons.append(f"High P/B ({_format_value(fundamental_data['price_to_book'])})")
                    
            # Growth Metrics
            if fundamental_data.get('revenue_growth'):
                if fundamental_data['revenue_growth'] > 0.2:  # 20% growth
                    score += 2
                    reasons.append(f"High revenue growth ({_format_value(fundamental_data['revenue_growth'])})")
                elif fundamental_data['revenue_growth'] > 0.1:  # 10% growth
                    score += 1
                    reasons.append(f"Moderate revenue growth ({_format_value(fundamental_data['revenue_growth'])})")
                elif fundamental_data['revenue_growth'] < 0:
                    score -= 1
                    reasons.append(f"Negative revenue growth ({_format_value(fundamental_data['revenue_growth'])})")
                    
            if fundamental_data.get('earnings_growth'):
                if fundamental_data['earnings_growth'] > 0.2:
                    score += 2
                    reasons.append(f"High earnings growth ({_format_value(fundamental_data['earnings_growth'])})")
                elif fundamental_data['earnings_growth'] > 0.1:
                    score += 1
                    reasons.append(f"Moderate earnings growth ({_format_value(fundamental_data['earnings_growth'])})")
                elif fundamental_data['earnings_growth'] < 0:
                    score -= 1
                    reasons.append(f"Negative earnings growth ({_format_value(fundamental_data['earnings_growth'])})")
                    
            # Financial Health Metrics
            if fundamental_data.get('debt_to_equity'):
                if fundamental_data['debt_to_equity'] < 0.5:
                    score += 2
                    reasons.append(f"Low debt-to-equity ({_format_value(fundamental_data['debt_to_equity'])})")
                elif fundamental_data['debt_to_equity'] < 1:
                    score += 1
                    reasons.append(f"Moderate debt-to-equity ({_format_value(fundamental_data['debt_to_equity'])})")
                elif fundamental_data['debt_to_equity'] > 2:
                    score -= 1
                    reasons.append(f"High debt-to-equity ({_format_value(fundamental_data['debt_to_equity'])})")
                    
            if fundamental_data.get('current_ratio'):
                if fundamental_data['current_ratio'] > 2:
                    score += 2
                    reasons.append(f"High current ratio ({_format_value(fundamental_data['current_ratio'])})")
                elif fundamental_data['current_ratio'] > 1.5:
                    score += 1
                    reasons.append(f"Healthy current ratio ({_format_value(fundamental_data['current_ratio'])})")
                elif fundamental_data['current_ratio'] < 1:
                    score -= 1
                    reasons.append(f"Low current ratio ({_format_value(fundamental_data['current_ratio'])})")
                    
            # Profitability Metrics
            if fundamental_data.get('profit_margins'):
                if fundamental_data['profit_margins'] > 0.2:
                    score += 2
                    reasons.append(f"High profit margins ({_format_value(fundamental_data['profit_margins'])})")
                elif fundamental_data['profit_margins'] > 0.1:
                    score += 1
                    reasons.append(f"Moderate profit margins ({_format_value(fundamental_data['profit_margins'])})")
                elif fundamental_data['profit_margins'] < 0:
                    score -= 2
                    reasons.append(f"Negative profit margins ({_format_value(fundamental_data['profit_margins'])})")
                    
            if fundamental_data.get('return_on_equity'):
                if fundamental_data['return_on_equity'] > 0.2:
                    score += 2
                    reasons.append(f"High ROE ({_format_value(fundamental_data['return_on_equity'])})")
                elif fundamental_data['return_on_equity'] > 0.15:
                    score += 1
                    reasons.append(f"Good ROE ({_format_value(fundamental_data['return_on_equity'])})")
                elif fundamental_data['return_on_equity'] < 0:
                    score -= 1
                    reasons.append(f"Negative ROE ({_format_value(fundamental_data['return_on_equity'])})")
            
            # Map score to label
            if score >= 3:
                label = "STRONG BUY"
            elif score > 0:
                label = "BUY"
            elif score < -1:
                label = "SELL"
            else:
                label = "HOLD"

            # Build short summary
            if reasons:
                summary = ", ".join(reasons[:4]) + ("..." if len(reasons) > 4 else "")
            else:
                summary = "No strong fundamental signals detected."

            return {"label": label, "summary": summary}
                
        except Exception as e:
            print(f"Error in fundamental recommendation: {e}")
            return {"label": "HOLD", "summary": "Error computing fundamental recommendation."}

    def get_technical_recommendation(self, technical_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate recommendation based on technical analysis.

        Returns a dict with keys: 'label' and 'summary' (short rationale).
        """
        try:
            signals = 0
            reasons = []
            
            # Momentum Indicators
            # RSI Analysis
            if technical_data.get('rsi'):
                rsi = technical_data['rsi']
                if rsi < 30:  # Oversold
                    signals += 2
                    reasons.append(f"RSI oversold ({_format_value(rsi)})")
                elif rsi < 40:
                    signals += 1
                    reasons.append(f"RSI low ({_format_value(rsi)})")
                elif rsi > 70:  # Overbought
                    signals -= 2
                    reasons.append(f"RSI overbought ({_format_value(rsi)})")
                elif rsi > 60:
                    signals -= 1
                    reasons.append(f"RSI high ({_format_value(rsi)})")
            
            # Stochastic Oscillator
            if technical_data.get('stoch_k') and technical_data.get('stoch_d'):
                stoch_k = technical_data['stoch_k']
                stoch_d = technical_data['stoch_d']
                if stoch_k < 20 and stoch_d < 20:  # Oversold
                    signals += 2
                    reasons.append(f"Stochastic oversold (K={_format_value(stoch_k)}, D={_format_value(stoch_d)})")
                elif stoch_k > 80 and stoch_d > 80:  # Overbought
                    signals -= 2
                    reasons.append(f"Stochastic overbought (K={_format_value(stoch_k)}, D={_format_value(stoch_d)})")
                # Stochastic crossover
                if stoch_k > stoch_d:
                    signals += 1
                    reasons.append("Stochastic K above D")
                else:
                    signals -= 1
                    reasons.append("Stochastic K below D")
            
            # MACD Analysis
            if all(key in technical_data for key in ['macd', 'macd_signal', 'macd_hist']):
                # MACD crossover
                if technical_data['macd'] > technical_data['macd_signal']:
                    signals += 2
                    reasons.append("MACD bullish crossover")
                else:
                    signals -= 1
                    reasons.append("MACD bearish crossover")
                # MACD histogram trend
                if technical_data['macd_hist'] > 0:
                    signals += 1
                    reasons.append("Positive MACD histogram")
                    
            # Trend Indicators
            # ADX Analysis (Trend Strength)
            if technical_data.get('adx'):
                adx = technical_data['adx']
                if adx > 25:  # Strong trend
                    if technical_data.get('adx_positive', 0) > technical_data.get('adx_negative', 0):
                        signals += 2
                        reasons.append(f"Strong ADX uptrend ({_format_value(adx)})")
                    else:
                        signals -= 2
                        reasons.append(f"Strong ADX downtrend ({_format_value(adx)})")
                        
            # Moving Averages
            if technical_data.get('above_sma_20'):
                signals += 1
                reasons.append("Price above SMA20")
            else:
                signals -= 1
                reasons.append("Price below SMA20")
                
            if technical_data.get('above_sma_50'):
                signals += 1
                reasons.append("Price above SMA50")
            else:
                signals -= 1
                reasons.append("Price below SMA50")
                
            if technical_data.get('sma_20_cross_50'):  # Golden Cross
                signals += 2
                reasons.append("SMA20 crossed above SMA50 (golden cross)")
                
            # Bollinger Bands Analysis
            if all(key in technical_data for key in ['current_price', 'bb_upper', 'bb_lower', 'bb_width']):
                price = technical_data['current_price']
                if price < technical_data['bb_lower']:
                    signals += 2  # Oversold
                    reasons.append("Price below lower Bollinger Band")
                elif price > technical_data['bb_upper']:
                    signals -= 2  # Overbought
                    reasons.append("Price above upper Bollinger Band")
                    
                # Volatility consideration
                if technical_data['bb_width'] > 0.2:  # High volatility
                    signals = int(signals * 0.8)  # Reduce signal strength
                    reasons.append("High Bollinger band width (high volatility)")
                    
            # Volume Indicators
            if technical_data.get('mfi'):  # Money Flow Index
                mfi = technical_data['mfi']
                if mfi < 20:
                    signals += 2
                    reasons.append(f"MFI oversold ({_format_value(mfi)})")
                elif mfi > 80:
                    signals -= 2
                    reasons.append(f"MFI overbought ({_format_value(mfi)})")
            
            # Map signals to label
            if signals >= 3:
                label = "STRONG BUY"
            elif signals > 0:
                label = "BUY"
            elif signals < -1:
                label = "SELL"
            else:
                label = "HOLD"

            if reasons:
                summary = ", ".join(reasons[:4]) + ("..." if len(reasons) > 4 else "")
            else:
                summary = "No strong technical signals detected."

            return {"label": label, "summary": summary}
                
        except Exception as e:
            print(f"Error in technical recommendation: {e}")
            return {"label": "HOLD", "summary": "Error computing technical recommendation."}

    def get_recommendation(self, ticker: str) -> Dict[str, str]:
        """
        Get comprehensive buy/sell/hold recommendations for a stock.
        
        Args:
            ticker (str): The stock ticker symbol
            
        Returns:
            Dict[str, str]: Recommendations from different analyses
        """
        analysis = self.analyze_stock(ticker)
        fundamental_rec = self.get_fundamental_recommendation(analysis["fundamental_analysis"])
        technical_rec = self.get_technical_recommendation(analysis["technical_analysis"])

        # Short-term (1 week): Use technicals only
        short_label = technical_rec.get('label') if isinstance(technical_rec, dict) else technical_rec
        short_summary = technical_rec.get('summary', '') if isinstance(technical_rec, dict) else ''

        # Medium-term (3 months): Blend technical and fundamental
        rec_scores = {
            "STRONG BUY": 2,
            "BUY": 1,
            "HOLD": 0,
            "SELL": -1
        }
        f_label = fundamental_rec.get('label') if isinstance(fundamental_rec, dict) else fundamental_rec
        t_label = technical_rec.get('label') if isinstance(technical_rec, dict) else technical_rec
        medium_score = rec_scores.get(f_label, 0) + rec_scores.get(t_label, 0)
        if medium_score >= 2:
            medium_label = "STRONG BUY"
        elif medium_score > 0:
            medium_label = "BUY"
        elif medium_score < -1:
            medium_label = "SELL"
        else:
            medium_label = "HOLD"
        medium_summary = []
        if isinstance(fundamental_rec, dict) and fundamental_rec.get('summary'):
            medium_summary.append(f"Fundamentals: {fundamental_rec.get('summary')}")
        if isinstance(technical_rec, dict) and technical_rec.get('summary'):
            medium_summary.append(f"Technical: {technical_rec.get('summary')}")
        medium_summary = " | ".join(medium_summary) if medium_summary else "No combined rationale available."

        # Long-term (6-12 months): Use fundamentals only
        long_label = fundamental_rec.get('label') if isinstance(fundamental_rec, dict) else fundamental_rec
        long_summary = fundamental_rec.get('summary', '') if isinstance(fundamental_rec, dict) else ''

        return {
            "short_term": {"label": short_label, "summary": short_summary},
            "medium_term": {"label": medium_label, "summary": medium_summary},
            "long_term": {"label": long_label, "summary": long_summary},
            "fundamental": fundamental_rec,
            "technical": technical_rec
        }

    def find_ticker(self, company_name: str) -> Dict[str, Any]:
        """
        Search for a company's ticker symbol by name.
        
        Args:
            company_name (str): The name of the company to search for
            
        Returns:
            Dict[str, Any]: Search results with possible matches
        """
        return self.company_searcher.analyze(company_name)

    def get_best_ticker_match(self, company_name: str) -> Optional[str]:
        """
        Get the most likely ticker symbol for a company name.
        
        Args:
            company_name (str): The name of the company
            
        Returns:
            Optional[str]: The most likely ticker symbol, or None if no match found
        """
        return self.company_searcher.get_best_match(company_name)
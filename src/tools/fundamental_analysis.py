import yfinance as yf
from typing import Dict, Any
from .base import AnalysisTool

class FundamentalAnalysis(AnalysisTool):
    def analyze(self, ticker: str) -> Dict[str, Any]:
        """
        Perform fundamental analysis on a stock.
        
        Args:
            ticker (str): The stock ticker symbol
            
        Returns:
            Dict[str, Any]: Fundamental analysis results
        """
        try:
            stock = yf.Ticker(ticker)
            info = stock.info

            # Fetch news articles (headlines and one-line summary)
            news_items = []
            try:
                news = stock.news if hasattr(stock, 'news') else []
            except Exception:
                news = []
            for item in news[:5]:
                headline = item.get('title') or item.get('headline')
                summary = item.get('summary') or item.get('publisher') or ''
                url = item.get('link') or item.get('url')
                news_items.append({
                    'headline': headline,
                    'summary': summary,
                    'url': url
                })

            # Extract relevant fundamental metrics
            analysis = {
                # Valuation Metrics
                "market_cap": info.get("marketCap"),
                "pe_ratio": info.get("trailingPE"),
                "forward_pe": info.get("forwardPE"),
                "peg_ratio": info.get("pegRatio"),
                "price_to_book": info.get("priceToBook"),
                "price_to_sales": info.get("priceToSalesTrailing12Months"),
                "enterprise_value": info.get("enterpriseValue"),
                "enterprise_to_revenue": info.get("enterpriseToRevenue"),
                "enterprise_to_ebitda": info.get("enterpriseToEbitda"),
                # Growth Metrics
                "revenue_growth": info.get("revenueGrowth"),
                "earnings_growth": info.get("earningsGrowth"),
                "earnings_quarterly_growth": info.get("earningsQuarterlyGrowth"),
                # Financial Health Metrics
                "debt_to_equity": info.get("debtToEquity"),
                "current_ratio": info.get("currentRatio"),
                "quick_ratio": info.get("quickRatio"),
                "total_cash": info.get("totalCash"),
                "total_debt": info.get("totalDebt"),
                # Profitability Metrics
                "profit_margins": info.get("profitMargins"),
                "operating_margins": info.get("operatingMargins"),
                "gross_margins": info.get("grossMargins"),
                "return_on_equity": info.get("returnOnEquity"),
                "return_on_assets": info.get("returnOnAssets"),
                # Dividend Metrics
                "dividend_yield": info.get("dividendYield"),
                "payout_ratio": info.get("payoutRatio"),
                "dividend_rate": info.get("dividendRate"),
                # Efficiency Metrics
                "inventory_turnover": info.get("inventoryTurnover"),
                "asset_turnover": info.get("assetTurnover"),
                # News Articles
                "news": news_items
            }
            return analysis
        except Exception as e:
            return {"error": str(e)}
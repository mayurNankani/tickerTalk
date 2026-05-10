"""
Fundamental Analysis Tool
Analyzes fundamental metrics including valuation, growth, financial health, and profitability.
"""

import yfinance as yf
from typing import Dict, Any, List
from .base import AnalysisTool, ToolResult, ResultStatus


class FundamentalAnalysis(AnalysisTool):
    """Performs fundamental analysis on stocks using financial metrics"""
    
    def analyze(self, ticker: str, **kwargs) -> ToolResult:
        """
        Perform comprehensive fundamental analysis on a stock.
        
        Args:
            ticker: The stock ticker symbol
            **kwargs: Additional parameters (currently unused)
            
        Returns:
            ToolResult containing fundamental metrics and news
        """
        # Validate ticker
        if not self._validate_ticker(ticker):
            return ToolResult(
                status=ResultStatus.ERROR,
                error="Invalid ticker format"
            )
        
        try:
            ticker = ticker.upper().strip()
            stock = yf.Ticker(ticker)
            info = stock.info
            
            # Check if we got valid data
            if not info or ('symbol' not in info and 'regularMarketPrice' not in info):
                return ToolResult(
                    status=ResultStatus.NO_DATA,
                    error=f"No data available for {ticker}"
                )
            
            # Extract fundamental metrics
            analysis_data = self._extract_metrics(info)
            
            # Fetch news articles
            analysis_data['news'] = self._fetch_news(stock)
            
            return ToolResult(
                status=ResultStatus.SUCCESS,
                data=analysis_data,
                metadata={'ticker': ticker, 'source': 'yfinance'}
            )
            
        except Exception as e:
            return self._handle_error(e, ticker)
    
    def _extract_metrics(self, info: Dict[str, Any]) -> Dict[str, Any]:
        """Extract and organize fundamental metrics from stock info"""
        return {
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
        }
    
    def _fetch_news(self, stock: yf.Ticker) -> List[Dict[str, str]]:
        """Fetch recent news articles for the stock"""
        news_items = []
        try:
            news = stock.news if hasattr(stock, 'news') else []
            for item in news[:5]:
                news_items.append({
                    'headline': item.get('title') or item.get('headline', ''),
                    'summary': item.get('summary') or item.get('publisher', ''),
                    'url': item.get('link') or item.get('url', '')
                })
        except Exception as e:
            self.logger.warning(f"Could not fetch news: {e}")
        return news_items

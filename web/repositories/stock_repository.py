"""
Stock Data Repository
Data access layer for stock information from external sources
"""

import sys
import os
from typing import Dict, Any, Optional, List
from abc import ABC, abstractmethod

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from adapters.company_lookup.yahoo_company_lookup_adapter import YahooCompanyLookupAdapter
from adapters.market_data.yahoo_finance_adapter import YahooFinanceAdapter
from src.agent_improved import StockAnalysisAgentImproved as StockAnalysisAgent
from adapters.news.finnhub_adapter import FinnhubNewsAdapter

# Ensure web/ directory is on sys.path so sibling packages (utils) can be imported
_web_dir = os.path.abspath(os.path.dirname(__file__) + '/..')
if _web_dir not in sys.path:
    sys.path.insert(0, _web_dir)
from utils.cache import quote_cache, news_cache, history_cache


class IStockRepository(ABC):
    """Interface for stock data access"""
    
    @abstractmethod
    def search_company(self, query: str) -> Optional[Dict[str, Any]]:
        """Search for company by name or ticker"""
        pass
    
    @abstractmethod
    def get_quote(self, ticker: str) -> Dict[str, Any]:
        """Get current stock quote"""
        pass
    
    @abstractmethod
    def get_recommendations(self, ticker: str) -> Dict[str, Any]:
        """Get stock recommendations"""
        pass
    
    @abstractmethod
    def get_news(self, ticker: str) -> Dict[str, Any]:
        """Get news articles"""
        pass
    
    @abstractmethod
    def get_price_history(self, ticker: str, period: str) -> Dict[str, List]:
        """Get historical price data"""
        pass
    
    @abstractmethod
    def get_earnings(self, ticker: str) -> Dict[str, Any]:
        """Get earnings data"""
        pass


class StockRepository(IStockRepository):
    """
    Concrete implementation of stock data repository
    Aggregates data from multiple sources
    """
    
    def __init__(self):
        self.company_lookup = YahooCompanyLookupAdapter()
        self.market_data = YahooFinanceAdapter()
        self.analysis_agent = StockAnalysisAgent()
        self.news_adapter = FinnhubNewsAdapter()
    
    def search_company(self, query: str) -> Optional[Dict[str, Any]]:
        """Search for company and return best match (transitional dict)."""
        print(f"[DEBUG] Repository search_company called with: '{query}'")
        identities = self.company_lookup.search(query, limit=5)
        if not identities:
            print("[DEBUG] No identities found")
            return None
        top = identities[0]
        result = {
            'symbol': top.symbol,
            'long_name': top.long_name,
            'short_name': top.short_name,
        }
        print(f"[DEBUG] Returning match: {result}")
        return result
    
    def validate_ticker(self, ticker: str) -> bool:
        """Validate ticker by ensuring quote has a price."""
        quote = self.market_data.get_quote(ticker)
        return quote.price is not None
    
    def get_quote(self, ticker: str) -> Dict[str, Any]:
        """Get current stock quote (transitional wrapper, cached)."""
        key = f"quote:{ticker}"
        cached = quote_cache.get(key)
        if cached is not None:
            return cached
        quote = self.market_data.get_quote(ticker)
        result = {
            "status": "ok" if quote.price is not None else "error",
            "data": {
                "symbol": quote.symbol,
                "price": quote.price,
                "currency": quote.currency,
                "name": quote.name
            },
            "error": None if quote.price is not None else "Quote unavailable"
        }
        if quote.price is not None:
            quote_cache.set(key, result)
        return result
    
    def get_recommendations(self, ticker: str) -> Dict[str, Any]:
        """Get stock analysis recommendations"""
        return self.analysis_agent.get_recommendation(ticker)
    
    def get_news(self, ticker: str) -> Dict[str, Any]:
        """Get news articles for ticker (adapter-backed, cached)."""
        key = f"news:{ticker}"
        cached = news_cache.get(key)
        if cached is not None:
            return cached
        articles = self.news_adapter.get_company_news(ticker, limit=15)
        # Transitional shape preserving existing expectations
        serialized = []
        for a in articles:
            serialized.append({
                "headline": a.headline,
                "summary": a.summary,
                "url": a.url,
                "source": a.source or "Finnhub",
                "datetime": a.published_at.strftime('%Y-%m-%d %H:%M'),
            })
        result = {"news": serialized}
        news_cache.set(key, result)
        return result
    
    def get_price_history(self, ticker: str, period: str = '1mo') -> Dict[str, List]:
        """Fetch historical price data (simplified adapter-backed, cached)."""
        key = f"history:{ticker}:{period}"
        cached = history_cache.get(key)
        if cached is not None:
            return cached
        history = self.market_data.get_price_history(ticker, period)
        # Include time component for intraday periods
        if period in ('1d', '5d'):
            dates = [c.timestamp.strftime('%Y-%m-%d %H:%M') for c in history.candles]
        else:
            dates = [c.timestamp.strftime('%Y-%m-%d') for c in history.candles]
        prices = [round(c.close, 2) if c.close is not None else None for c in history.candles]
        result = {"dates": dates, "prices": prices}
        history_cache.set(key, result)
        return result
    
    def get_earnings(self, ticker: str) -> Dict[str, Any]:
        """Get earnings data"""
        # Temporarily still using original agent for earnings until adapter added
        from src.mcp_agent import YahooFinanceAgent  # local import to reduce top-level legacy dependency
        return YahooFinanceAgent().handle({
            "action": "get_earnings",
            "parameters": {"ticker": ticker}
        })
    
    def get_stock_info(self, ticker: str) -> Dict[str, Any]:
        """Get comprehensive stock info from yfinance"""
        import yfinance as yf
        
        try:
            stock = yf.Ticker(ticker)
            return stock.info
        except Exception as e:
            print(f"Error fetching info for {ticker}: {e}")
            return {"error": str(e)}

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

from src.tools.company_search import CompanySearch
from src.mcp_agent import YahooFinanceAgent
from src.agent import StockAnalysisAgent
from src.tools.rss_news import RSSNewsAgent


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
        self.company_search = CompanySearch()
        self.yahoo_agent = YahooFinanceAgent()
        self.analysis_agent = StockAnalysisAgent()
        self.news_agent = RSSNewsAgent()
    
    def search_company(self, query: str) -> Optional[Dict[str, Any]]:
        """Search for company and return best match"""
        search_result = self.company_search.analyze(query)
        
        # Handle ToolResult return type
        if hasattr(search_result, 'data'):
            matches = search_result.data.get('matches', []) if search_result.data else []
        else:
            matches = search_result.get('matches', [])
        
        return matches[0] if matches else None
    
    def validate_ticker(self, ticker: str) -> bool:
        """Validate if ticker exists by attempting to get quote"""
        try:
            quote_result = self.yahoo_agent.handle({
                "action": "get_quote",
                "parameters": {"ticker": ticker}
            })
            return isinstance(quote_result, dict) and quote_result.get('status') == 'ok'
        except Exception:
            return False
    
    def get_quote(self, ticker: str) -> Dict[str, Any]:
        """Get current stock quote"""
        return self.yahoo_agent.handle({
            "action": "get_quote",
            "parameters": {"ticker": ticker}
        })
    
    def get_recommendations(self, ticker: str) -> Dict[str, Any]:
        """Get stock analysis recommendations"""
        return self.analysis_agent.get_recommendation(ticker)
    
    def get_news(self, ticker: str) -> Dict[str, Any]:
        """Get news articles for ticker"""
        news_result_obj = self.news_agent.analyze(ticker)
        
        # Handle ToolResult return type
        if hasattr(news_result_obj, 'data'):
            return news_result_obj.data if news_result_obj.data else {'news': []}
        else:
            return news_result_obj
    
    def get_price_history(self, ticker: str, period: str = '1mo') -> Dict[str, List]:
        """Fetch historical price data for charting"""
        import yfinance as yf
        
        try:
            interval_map = {
                '1d': '5m',
                '5d': '15m',
                '1mo': '30m'
            }
            
            fallback_map = {
                '1d': ['5m', '15m', '30m', '60m', None],
                '5d': ['15m', '30m', '60m', None],
                '1mo': ['30m', '60m', '1d', None]
            }
            
            preferred_list = fallback_map.get(period, [None])
            stock = yf.Ticker(ticker)
            
            hist = None
            min_points = 8
            used_interval = None
            
            for iv in preferred_list:
                try:
                    if iv:
                        candidate = stock.history(period=period, interval=iv)
                    else:
                        candidate = stock.history(period=period)
                    
                    if candidate is None or candidate.empty:
                        continue
                    
                    if len(candidate) >= min_points or iv is None:
                        hist = candidate
                        used_interval = iv
                        break
                    else:
                        if hist is None or len(candidate) > len(hist):
                            hist = candidate
                            used_interval = iv
                        continue
                except Exception:
                    continue
            
            if hist is None or hist.empty:
                return {'dates': [], 'prices': []}
            
            fmt = '%Y-%m-%d %H:%M' if used_interval and ('m' in str(used_interval) or 'h' in str(used_interval)) else '%Y-%m-%d'
            
            dates = [dt.strftime(fmt) for dt in hist.index]
            prices = hist['Close'].round(2).tolist()
            
            return {'dates': dates, 'prices': prices}
            
        except Exception as e:
            print(f"Error fetching price history for {ticker}: {e}")
            return {'dates': [], 'prices': []}
    
    def get_earnings(self, ticker: str) -> Dict[str, Any]:
        """Get earnings data"""
        return self.yahoo_agent.handle({
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

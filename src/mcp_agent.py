"""
Model Context Protocol (MCP) Agent System
Provides a standardized interface for external data sources and services.
"""

import logging
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass
from enum import Enum

import yfinance as yf

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AgentStatus(Enum):
    """Standard status codes for agent operations"""
    OK = "ok"
    ERROR = "error"
    NO_DATA = "no_data"


@dataclass
class AgentResponse:
    """Standardized response from MCP agents"""
    status: AgentStatus
    data: Optional[Any] = None
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'status': self.status.value,
            'data': self.data,
            'error': self.error
        }


class MCPAgent:
    """
    Base class for all Model Context Protocol (MCP) agents.
    Provides standardized request/response handling and action dispatching.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self._actions: Dict[str, Callable] = {}
        self._register_actions()
    
    def _register_actions(self):
        """Register available actions - override in subclasses"""
        pass
    
    def handle(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle an incoming request and dispatch to appropriate action.
        
        Args:
            request: Dictionary with 'action' and 'parameters' keys
            
        Returns:
            Standardized response dictionary
        """
        try:
            action = request.get("action")
            params = request.get("parameters", {})
            
            if not action:
                return self._error_response("No action specified")
            
            # Check if action exists
            if not hasattr(self, action):
                return self._error_response(f"Unknown action: {action}")
            
            # Get method and execute
            method = getattr(self, action)
            result = method(**params)
            
            return {"status": "ok", "data": result, "error": None}
            
        except TypeError as e:
            error_msg = f"Invalid parameters for action '{action}': {str(e)}"
            self.logger.error(error_msg)
            return self._error_response(error_msg)
        except Exception as e:
            error_msg = f"Error executing action '{action}': {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            return self._error_response(error_msg)
    
    def _error_response(self, error: str) -> Dict[str, Any]:
        """Create standardized error response"""
        return {"status": "error", "error": error, "data": None}
    
    def _success_response(self, data: Any) -> Dict[str, Any]:
        """Create standardized success response"""
        return {"status": "ok", "data": data, "error": None}


class YahooFinanceAgent(MCPAgent):
    """
    Agent for fetching stock data from Yahoo Finance using yfinance library.
    Provides quote, earnings, and news data for stocks.
    """
    
    def __init__(self):
        super().__init__()
        self.cache = {}  # Simple in-memory cache
    
    def get_earnings(self, ticker: str) -> Dict[str, Any]:
        """
        Fetch earnings data including next earnings date and historical earnings.
        
        Args:
            ticker: Stock ticker symbol
            
        Returns:
            Dictionary with next_earnings and earnings_history
        """
        try:
            stock = yf.Ticker(ticker)
            
            # Get next earnings from calendar
            next_earnings = self._get_next_earnings(stock)
            
            # Get historical earnings
            earnings_history = self._get_earnings_history(stock)
            
            return {
                "symbol": ticker.upper(),
                "next_earnings": next_earnings,
                "earnings_history": earnings_history
            }
        except Exception as e:
            self.logger.error(f"Error fetching earnings for {ticker}: {e}")
            return {
                "symbol": ticker.upper(),
                "next_earnings": None,
                "earnings_history": [],
                "error": str(e)
            }
    
    def _get_next_earnings(self, stock: yf.Ticker) -> Optional[Dict[str, Any]]:
        """Extract next earnings date from stock calendar"""
        try:
            calendar = stock.calendar
            if calendar is not None and not calendar.empty:
                return {col: calendar.iloc[0][col] for col in calendar.columns}
        except Exception as e:
            self.logger.debug(f"Could not fetch calendar: {e}")
        return None
    
    def _get_earnings_history(self, stock: yf.Ticker) -> List[Dict[str, Any]]:
        """Extract historical earnings from earnings_dates"""
        earnings_list = []
        try:
            earnings_dates = stock.earnings_dates
            if earnings_dates is not None and not earnings_dates.empty:
                for idx, row in earnings_dates.head(10).iterrows():
                    record = {k: row[k] for k in earnings_dates.columns}
                    record['date'] = str(idx)
                    earnings_list.append(record)
        except Exception as e:
            self.logger.debug(f"Could not fetch earnings history: {e}")
        return earnings_list

    def get_quote(self, ticker: str) -> Dict[str, Any]:
        """
        Fetch current stock quote data.
        
        Args:
            ticker: Stock ticker symbol
            
        Returns:
            Dictionary with symbol, price, currency, and name
        """
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            
            return {
                "symbol": ticker.upper(),
                "price": info.get("regularMarketPrice") or info.get("currentPrice"),
                "currency": info.get("currency", "USD"),
                "name": info.get("shortName") or info.get("longName", ticker)
            }
        except Exception as e:
            self.logger.error(f"Error fetching quote for {ticker}: {e}")
            return {
                "symbol": ticker.upper(),
                "price": None,
                "currency": "USD",
                "name": ticker,
                "error": str(e)
            }

    def get_news(self, ticker: str, max_items: int = 5) -> Dict[str, Any]:
        """
        Fetch recent news articles for a stock.
        
        Args:
            ticker: Stock ticker symbol
            max_items: Maximum number of news items to return
            
        Returns:
            Dictionary with symbol and list of news items
        """
        try:
            stock = yf.Ticker(ticker)
            news_items = []
            
            # Get news from yfinance
            news_data = stock.news if hasattr(stock, 'news') else []
            
            for item in news_data[:max_items]:
                news_items.append({
                    "headline": item.get("title") or item.get("headline", ""),
                    "summary": item.get("summary") or item.get("publisher", ""),
                    "url": item.get("link") or item.get("url", "")
                })
            
            return {
                "symbol": ticker.upper(),
                "news": news_items
            }
        except Exception as e:
            self.logger.error(f"Error fetching news for {ticker}: {e}")
            return {
                "symbol": ticker.upper(),
                "news": [],
                "error": str(e)
            }
    
    def get_info(self, ticker: str) -> Dict[str, Any]:
        """
        Fetch comprehensive stock information.
        
        Args:
            ticker: Stock ticker symbol
            
        Returns:
            Full info dictionary from yfinance
        """
        try:
            stock = yf.Ticker(ticker)
            return stock.info
        except Exception as e:
            self.logger.error(f"Error fetching info for {ticker}: {e}")
            return {"error": str(e)}

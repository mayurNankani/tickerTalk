import json
import requests
from typing import Dict, Any

class MCPAgent:
    """
    Base class for all MCP agents. Handles JSON request/response.
    """
    def handle(self, request: Dict[str, Any]) -> Dict[str, Any]:
        try:
            action = request.get("action")
            params = request.get("parameters", {})
            # Dispatch to the appropriate method
            if not hasattr(self, action):
                return {"status": "error", "error": f"Unknown action: {action}", "data": None}
            method = getattr(self, action)
            result = method(**params)
            return {"status": "ok", "data": result, "error": None}
        except Exception as e:
            return {"status": "error", "error": str(e), "data": None}

# Example: YahooFinanceAgent
import yfinance as yf

class YahooFinanceAgent(MCPAgent):
    def get_quote(self, ticker: str) -> Dict[str, Any]:
        stock = yf.Ticker(ticker)
        info = stock.info
        return {
            "symbol": ticker,
            "price": info.get("regularMarketPrice"),
            "currency": info.get("currency"),
            "name": info.get("shortName")
        }

    def get_news(self, ticker: str) -> Dict[str, Any]:
        stock = yf.Ticker(ticker)
        news = []
        try:
            news_items = stock.news if hasattr(stock, 'news') else []
            for item in news_items[:5]:
                news.append({
                    "headline": item.get("title") or item.get("headline"),
                    "summary": item.get("summary") or item.get("publisher"),
                    "url": item.get("link") or item.get("url")
                })
        except Exception:
            pass
        return {"symbol": ticker, "news": news}

# Example: NewsAgent
class NewsAgent(MCPAgent):
    """
    Fetches news headlines from NewsAPI.org (or similar service).
    """
    NEWS_API_KEY = "YOUR_NEWSAPI_KEY"  # Replace with your NewsAPI.org key
    NEWS_ENDPOINT = "https://newsapi.org/v2/everything"

    def get_news(self, query: str, max_results: int = 5) -> dict:
        params = {
            "q": query,
            "apiKey": self.NEWS_API_KEY,
            "pageSize": max_results,
            "sortBy": "publishedAt",
            "language": "en"
        }
        try:
            resp = requests.get(self.NEWS_ENDPOINT, params=params, timeout=10)
            resp.raise_for_status()
            articles = resp.json().get("articles", [])
            news = []
            for article in articles:
                news.append({
                    "headline": article.get("title"),
                    "summary": article.get("description"),
                    "url": article.get("url")
                })
            return {"status": "ok", "data": {"query": query, "news": news}, "error": None}
        except Exception as e:
            return {"status": "error", "data": None, "error": str(e)}

"""
Finnhub News Agent
Fetches news articles from Finnhub API.
"""

import requests
from typing import List, Dict, Any
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
from .base import DataFetcher, ToolResult, ResultStatus

# Load environment variables from .env file if it exists (doesn't override existing env vars)
load_dotenv(override=False)


class FinnhubNewsAgent(DataFetcher):
    """Fetches news headlines from Finnhub API"""
    
    BASE_URL = 'https://finnhub.io/api/v1'
    
    def __init__(self):
        super().__init__()
        # Get API key from environment variable
        self.api_key = os.getenv('FINNHUB_API_KEY', '')
        if not self.api_key:
            self.logger.warning("FINNHUB_API_KEY not set in environment variables")
        else:
            # Log first/last 4 chars for debugging (mask the middle)
            masked_key = f"{self.api_key[:4]}...{self.api_key[-4:]}" if len(self.api_key) > 8 else "****"
            self.logger.info(f"Finnhub API key loaded: {masked_key}")
    
    def fetch(self, query: str, max_items: int = 5, days_back: int = 7, **kwargs) -> ToolResult:
        """
        Fetch news articles for a stock ticker.
        
        Args:
            query: Stock ticker symbol
            max_items: Maximum number of articles to fetch
            days_back: How many days back to fetch news (default: 7)
            **kwargs: Additional parameters
            
        Returns:
            ToolResult containing news articles
        """
        if not query or not isinstance(query, str):
            return ToolResult(
                status=ResultStatus.ERROR,
                error="Invalid ticker symbol"
            )
        
        if not self.api_key:
            return ToolResult(
                status=ResultStatus.ERROR,
                error="Finnhub API key not configured. Set FINNHUB_API_KEY environment variable.",
                data={'news': []}
            )
        
        try:
            ticker = query.upper().strip()
            
            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days_back)
            
            # Format dates as YYYY-MM-DD
            from_date = start_date.strftime('%Y-%m-%d')
            to_date = end_date.strftime('%Y-%m-%d')
            
            # Fetch company news
            url = f"{self.BASE_URL}/company-news"
            params = {
                'symbol': ticker,
                'from': from_date,
                'to': to_date,
                'token': self.api_key
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            news_data = response.json()
            
            if not news_data or not isinstance(news_data, list):
                return ToolResult(
                    status=ResultStatus.NO_DATA,
                    data={'news': []},
                    error=f"No news articles found for {ticker}"
                )
            
            # Extract and format news articles
            news_articles = self._extract_articles(news_data, max_items)
            
            if not news_articles:
                return ToolResult(
                    status=ResultStatus.NO_DATA,
                    data={'news': []},
                    error=f"No news articles found for {ticker}"
                )
            
            return ToolResult(
                status=ResultStatus.SUCCESS,
                data={'news': news_articles},
                metadata={
                    'ticker': ticker,
                    'source': 'finnhub',
                    'date_range': f"{from_date} to {to_date}"
                }
            )
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"HTTP error fetching Finnhub news for {query}: {e}")
            return ToolResult(
                status=ResultStatus.ERROR,
                error=f"Failed to fetch news: {str(e)}",
                data={'news': []}
            )
        except Exception as e:
            self.logger.error(f"Error fetching Finnhub news for {query}: {e}")
            return ToolResult(
                status=ResultStatus.ERROR,
                error=f"Failed to fetch news: {str(e)}",
                data={'news': []}
            )
    
    def _extract_articles(self, news_data: List[Dict], max_items: int) -> List[Dict[str, str]]:
        """Extract and format news articles from Finnhub response"""
        articles = []
        
        # Sort by datetime (newest first)
        sorted_news = sorted(news_data, key=lambda x: x.get('datetime', 0), reverse=True)
        
        for item in sorted_news[:max_items]:
            # Convert Unix timestamp to readable date
            timestamp = item.get('datetime', 0)
            date_str = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M') if timestamp else 'N/A'
            
            articles.append({
                'headline': item.get('headline', ''),
                'summary': item.get('summary', '')[:300] + '...' if len(item.get('summary', '')) > 300 else item.get('summary', ''),
                'url': item.get('url', ''),
                'source': item.get('source', 'Unknown'),
                'datetime': date_str,
                'category': item.get('category', 'general')
            })
        
        return articles
    
    def analyze(self, ticker: str, **kwargs) -> ToolResult:
        """
        Legacy method for backward compatibility with AnalysisTool interface.
        """
        return self.fetch(ticker, **kwargs)

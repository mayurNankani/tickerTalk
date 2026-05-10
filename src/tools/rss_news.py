"""
RSS News Agent
Fetches news articles from Yahoo Finance RSS feeds.
"""

import feedparser
from typing import List, Dict, Any
from .base import DataFetcher, ToolResult, ResultStatus


class RSSNewsAgent(DataFetcher):
    """Fetches news headlines from Yahoo Finance RSS feeds"""
    
    TICKER_FEED_TEMPLATE = 'https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US'
    
    def fetch(self, query: str, max_items: int = 5, **kwargs) -> ToolResult:
        """
        Fetch news articles for a stock ticker.
        
        Args:
            query: Stock ticker symbol
            max_items: Maximum number of articles to fetch
            **kwargs: Additional parameters
            
        Returns:
            ToolResult containing news articles
        """
        if not query or not isinstance(query, str):
            return ToolResult(
                status=ResultStatus.ERROR,
                error="Invalid ticker symbol"
            )
        
        try:
            ticker = query.upper().strip()
            feed_url = self.TICKER_FEED_TEMPLATE.format(ticker=ticker)
            
            # Set User-Agent to avoid 403 errors
            feedparser.USER_AGENT = self._get_user_agent()
            
            # Parse the feed
            feed = feedparser.parse(feed_url)
            
            # Check for parse errors
            if hasattr(feed, 'bozo') and feed.bozo and not feed.entries:
                self.logger.warning(f"RSS feed parse error for {ticker}")
                return ToolResult(
                    status=ResultStatus.NO_DATA,
                    data={'news': []},
                    error="Could not parse RSS feed"
                )
            
            # Extract news articles
            news_articles = self._extract_articles(feed.entries, max_items)
            
            if not news_articles:
                return ToolResult(
                    status=ResultStatus.NO_DATA,
                    data={'news': []},
                    error=f"No news articles found for {ticker}"
                )
            
            return ToolResult(
                status=ResultStatus.SUCCESS,
                data={'news': news_articles},
                metadata={'ticker': ticker, 'source': 'yahoo_finance_rss'}
            )
            
        except Exception as e:
            self.logger.error(f"Error fetching RSS news for {query}: {e}")
            return ToolResult(
                status=ResultStatus.ERROR,
                error=f"Failed to fetch news: {str(e)}",
                data={'news': []}
            )
    
    def _extract_articles(self, entries: List, max_items: int) -> List[Dict[str, str]]:
        """Extract and format news articles from feed entries"""
        articles = []
        for entry in entries[:max_items]:
            articles.append({
                'headline': entry.get('title', ''),
                'summary': entry.get('summary', ''),
                'url': entry.get('link', '')
            })
        return articles
    
    def _get_user_agent(self) -> str:
        """Get User-Agent string for RSS requests"""
        return 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    
    def analyze(self, ticker: str, **kwargs) -> ToolResult:
        """
        Legacy method for backward compatibility with AnalysisTool interface.
        """
        return self.fetch(ticker, **kwargs)

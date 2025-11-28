import feedparser
from typing import List, Dict
from .base import AnalysisTool

class RSSNewsAgent(AnalysisTool):
    """
    Fetches news headlines from public RSS feeds (no API key required).
    """
    TICKER_FEED = 'https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US'

    def analyze(self, ticker: str = None) -> Dict[str, List[Dict]]:
        """
        Fetch news articles for a ticker only. If no ticker, return empty.
        """
        news = []
        if ticker:
            feed_url = self.TICKER_FEED.format(ticker=ticker)
            try:
                # Set User-Agent to avoid 403 errors
                feedparser.USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                d = feedparser.parse(feed_url)
                
                # Check if feed was successfully parsed
                if hasattr(d, 'bozo') and d.bozo and not d.entries:
                    print(f"Warning: RSS feed parse error for {ticker}")
                    return {'news': []}
                
                for entry in d.entries[:5]:
                    news.append({
                        'headline': entry.get('title', ''),
                        'summary': entry.get('summary', ''),
                        'url': entry.get('link', '')
                    })
            except Exception as e:
                print(f"Error fetching RSS news for {ticker}: {str(e)[:100]}")
                pass
        return {'news': news}

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
                d = feedparser.parse(feed_url)
                for entry in d.entries[:5]:
                    news.append({
                        'headline': entry.get('title', ''),
                        'summary': entry.get('summary', ''),
                        'url': entry.get('link', '')
                    })
            except Exception:
                pass
        return {'news': news}

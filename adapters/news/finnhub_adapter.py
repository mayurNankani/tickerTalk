"""Finnhub news adapter wrapping existing FinnhubNewsAgent.

Converts ToolResult output into domain NewsArticle objects. Keeps the existing
FinnhubNewsAgent for HTTP logic; adapter focuses on transformation and
interface compliance.
"""
from datetime import datetime
from typing import List
from core.models import NewsArticle
from .interface import NewsAdapter
from src.tools.finnhub_news import FinnhubNewsAgent

class FinnhubNewsAdapter(NewsAdapter):
    def __init__(self, agent: FinnhubNewsAgent | None = None):
        self._agent = agent or FinnhubNewsAgent()

    def get_company_news(self, symbol: str, limit: int = 20) -> List[NewsArticle]:
        result = self._agent.fetch(symbol, max_items=limit)
        if hasattr(result, 'data'):
            raw_list = (result.data or {}).get('news', [])
        else:
            raw_list = result.get('news', [])
        articles: List[NewsArticle] = []
        for item in raw_list:
            # item['datetime'] is a formatted string from existing extraction
            dt_raw = item.get('datetime')
            try:
                published = datetime.strptime(dt_raw, '%Y-%m-%d %H:%M') if dt_raw else datetime.utcnow()
            except Exception:
                published = datetime.utcnow()
            articles.append(
                NewsArticle(
                    headline=item.get('headline', ''),
                    summary=item.get('summary', ''),
                    url=item.get('url', ''),
                    published_at=published,
                    source=item.get('source', 'Finnhub'),
                )
            )
        return articles

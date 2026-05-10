"""Protocol for fetching normalized company news articles."""
from typing import Protocol, List
from core.models import NewsArticle

class NewsAdapter(Protocol):
    def get_company_news(self, symbol: str, limit: int = 20) -> List[NewsArticle]: ...

"""Protocol for performing sentiment analysis over news articles."""
from typing import Protocol, List
from core.models import NewsArticle, SentimentResult

class SentimentAdapter(Protocol):
    def analyze(self, articles: List[NewsArticle]) -> SentimentResult: ...

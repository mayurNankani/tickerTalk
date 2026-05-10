"""FinBERT sentiment adapter wrapping existing SentimentAnalyzer.

Transforms raw dict output into domain SentimentResult & enriches NewsArticle
objects with sentiment labels where possible.
"""
from typing import List
from core.models import NewsArticle, SentimentResult
from src.tools.sentiment_analysis import SentimentAnalyzer
from .interface import SentimentAdapter

class FinbertSentimentAdapter(SentimentAdapter):
    def __init__(self, analyzer: SentimentAnalyzer | None = None):
        self._analyzer = analyzer or SentimentAnalyzer()

    def analyze(self, articles: List[NewsArticle]) -> SentimentResult:
        # Convert domain articles to analyzer expected structure
        raw_articles = [
            {"headline": a.headline, "summary": a.summary} for a in articles
        ]
        result = self._analyzer.analyze_news_articles(raw_articles)
        # Build SentimentResult
        sentiment = SentimentResult(
            score=float(result.get("overall_score", 50.0)),
            confidence=float(result.get("confidence", 0.0)) / 100.0,  # scale to 0-1
            counts={
                "positive": int(result.get("positive_count", 0)),
                "negative": int(result.get("negative_count", 0)),
                "neutral": int(result.get("neutral_count", 0)),
            },
            articles=articles,
        )
        # Annotate articles with dominant label (optional)
        # The analyzer returns article_sentiments aligned to input order
        per_article = result.get("article_sentiments", [])
        for idx, art_sent in enumerate(per_article):
            if idx < len(articles):
                articles[idx].sentiment_label = art_sent.get("sentiment")
        return sentiment

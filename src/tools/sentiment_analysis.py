"""
FinBERT Sentiment Analysis
Analyzes financial news sentiment using FinBERT model locally.

Module-level singleton: the model is loaded once on first use and reused for
all subsequent calls — avoids the 2-3 second reload on every request.
"""

import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from typing import List, Dict, Any, Optional
import logging

_logger = logging.getLogger(__name__)

# --- Singleton state ----------------------------------------------------------
_singleton_tokenizer = None
_singleton_model = None
_singleton_device: Optional[str] = None
_singleton_load_failed: bool = False  # once True, skip all future load attempts


def _get_device() -> str:
    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


def _ensure_model_loaded(model_name: str = "ProsusAI/finbert") -> bool:
    """Load model into module-level singleton if not already done.

    Returns True if model is ready, False if it has permanently failed.
    """
    global _singleton_tokenizer, _singleton_model, _singleton_device, _singleton_load_failed
    if _singleton_model is not None:
        return True
    if _singleton_load_failed:
        return False
    try:
        _singleton_device = _get_device()
        _logger.info(f"Loading FinBERT singleton ({model_name}) on {_singleton_device}…")
        _singleton_tokenizer = AutoTokenizer.from_pretrained(model_name)
        _singleton_model = AutoModelForSequenceClassification.from_pretrained(model_name)
        _singleton_model.to(_singleton_device)
        _singleton_model.eval()
        _logger.info("FinBERT singleton loaded successfully.")
        return True
    except Exception as exc:
        _logger.error(f"FinBERT failed to load — sentiment will be unavailable: {exc}")
        _singleton_load_failed = True
        return False
# ------------------------------------------------------------------------------


class SentimentAnalyzer:
    """
    Local FinBERT sentiment analyzer for financial news.
    Uses ProsusAI/finbert model for financial sentiment classification.

    The underlying model/tokenizer are stored in module-level singletons so
    instantiating a new SentimentAnalyzer() never reloads the weights.
    """

    def __init__(self, model_name: str = "ProsusAI/finbert"):
        self.logger = logging.getLogger(__name__)
        self.model_name = model_name
        # Trigger singleton load (no-op if already loaded or permanently failed)
        _ensure_model_loaded(model_name)

    @property
    def tokenizer(self):
        return _singleton_tokenizer

    @property
    def model(self):
        return _singleton_model

    @property
    def device(self):
        return _singleton_device or "cpu"

    @property
    def model_available(self) -> bool:
        """True when the FinBERT model loaded successfully."""
        return _singleton_model is not None
    
    def analyze_text(self, text: str) -> Dict[str, Any]:
        """
        Analyze sentiment of a single text.
        
        Args:
            text: Text to analyze (headline or summary)
            
        Returns:
            Dict with sentiment label, score, and probabilities
        """
        if not self.model_available:
            return {
                'label': 'unavailable',
                'score': 0.0,
                'probabilities': {'positive': 0.0, 'negative': 0.0, 'neutral': 0.0},
                'unavailable': True,
            }
        
        try:
            # Tokenize input
            inputs = self.tokenizer(
                text,
                return_tensors="pt",
                truncation=True,
                max_length=512,
                padding=True
            ).to(self.device)
            
            # Get predictions
            with torch.no_grad():
                outputs = self.model(**inputs)
                predictions = torch.nn.functional.softmax(outputs.logits, dim=-1)
            
            # Extract probabilities
            probs = predictions[0].cpu().numpy()
            
            # FinBERT labels: [positive, negative, neutral]
            labels = ['positive', 'negative', 'neutral']
            label_probs = {labels[i]: float(probs[i]) for i in range(len(labels))}
            
            # Get dominant sentiment
            max_idx = probs.argmax()
            sentiment_label = labels[max_idx]
            confidence = float(probs[max_idx])
            
            return {
                'label': sentiment_label,
                'score': confidence,
                'probabilities': label_probs
            }
            
        except Exception as e:
            self.logger.error(f"Error analyzing sentiment: {e}")
            return {
                'label': 'unavailable',
                'score': 0.0,
                'probabilities': {'positive': 0.0, 'negative': 0.0, 'neutral': 0.0},
                'unavailable': True,
            }
    
    def analyze_news_articles(self, articles: List[Dict[str, str]]) -> Dict[str, Any]:
        """
        Analyze sentiment across multiple news articles.
        
        Args:
            articles: List of news articles with 'headline' and 'summary' keys
            
        Returns:
            Dict with aggregate sentiment score (0-100) and article-level sentiments
        """
        if not self.model_available:
            return {
                'overall_score': 50.0,
                'overall_sentiment': 'unavailable',
                'confidence': 0.0,
                'article_sentiments': [],
                'unavailable': True,
            }
        if not articles:
            return {
                'overall_score': 50.0,
                'overall_sentiment': 'neutral',
                'confidence': 0.0,
                'article_sentiments': []
            }
        
        article_results = []
        positive_count = 0
        negative_count = 0
        neutral_count = 0
        total_sentiment_score = 0.0
        
        for article in articles:
            # Analyze headline (more important) and summary
            headline = article.get('headline', '')
            summary = article.get('summary', '')
            
            # Weight headline more heavily (70% headline, 30% summary)
            headline_sentiment = self.analyze_text(headline) if headline else None
            summary_sentiment = self.analyze_text(summary) if summary else None
            
            if headline_sentiment and summary_sentiment:
                # Combine with weighting
                combined_probs = {
                    'positive': headline_sentiment['probabilities']['positive'] * 0.7 + 
                               summary_sentiment['probabilities']['positive'] * 0.3,
                    'negative': headline_sentiment['probabilities']['negative'] * 0.7 + 
                               summary_sentiment['probabilities']['negative'] * 0.3,
                    'neutral': headline_sentiment['probabilities']['neutral'] * 0.7 + 
                              summary_sentiment['probabilities']['neutral'] * 0.3
                }
            elif headline_sentiment:
                combined_probs = headline_sentiment['probabilities']
            elif summary_sentiment:
                combined_probs = summary_sentiment['probabilities']
            else:
                continue
            
            # Determine overall label
            max_label = max(combined_probs.items(), key=lambda x: x[1])
            sentiment_label = max_label[0]
            confidence = max_label[1]
            
            # Count sentiments
            if sentiment_label == 'positive':
                positive_count += 1
            elif sentiment_label == 'negative':
                negative_count += 1
            else:
                neutral_count += 1
            
            # Calculate sentiment score (-1 to 1)
            article_score = combined_probs['positive'] - combined_probs['negative']
            total_sentiment_score += article_score
            
            article_results.append({
                'headline': headline,
                'sentiment': sentiment_label,
                'confidence': confidence,
                'score': article_score,
                'probabilities': combined_probs
            })
        
        # Calculate overall sentiment score (0-100 scale)
        if article_results:
            avg_sentiment = total_sentiment_score / len(article_results)
            # Convert from [-1, 1] to [0, 100]
            overall_score = (avg_sentiment + 1) * 50
            
            # Determine overall sentiment label
            if overall_score >= 60:
                overall_sentiment = 'positive'
            elif overall_score <= 40:
                overall_sentiment = 'negative'
            else:
                overall_sentiment = 'neutral'
            
            # Calculate confidence based on agreement
            total_articles = len(article_results)
            max_count = max(positive_count, negative_count, neutral_count)
            confidence = max_count / total_articles if total_articles > 0 else 0.0
        else:
            overall_score = 50.0
            overall_sentiment = 'neutral'
            confidence = 0.0
        
        return {
            'overall_score': overall_score,
            'overall_sentiment': overall_sentiment,
            'confidence': confidence * 100,  # 0-100%
            'article_count': len(article_results),
            'positive_count': positive_count,
            'negative_count': negative_count,
            'neutral_count': neutral_count,
            'article_sentiments': article_results
        }
    
    def is_available(self) -> bool:
        """Check if sentiment analysis is available"""
        return self.model_available

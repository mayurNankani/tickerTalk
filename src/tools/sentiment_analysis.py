"""
FinBERT Sentiment Analysis
Analyzes financial news sentiment using FinBERT model locally.
"""

import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from typing import List, Dict, Any
import logging


class SentimentAnalyzer:
    """
    Local FinBERT sentiment analyzer for financial news.
    Uses ProsusAI/finbert model for financial sentiment classification.
    """
    
    def __init__(self, model_name: str = "ProsusAI/finbert"):
        """
        Initialize the FinBERT sentiment analyzer.
        
        Args:
            model_name: HuggingFace model name (default: ProsusAI/finbert)
        """
        self.logger = logging.getLogger(__name__)
        self.model_name = model_name
        self.tokenizer = None
        self.model = None
        
        # Use MPS (Metal Performance Shaders) for Apple Silicon (M1/M2/M3)
        if torch.backends.mps.is_available():
            self.device = "mps"
        elif torch.cuda.is_available():
            self.device = "cuda"
        else:
            self.device = "cpu"
        
        try:
            self._load_model()
        except Exception as e:
            self.logger.error(f"Failed to load FinBERT model: {e}")
            self.logger.warning("Sentiment analysis will not be available")
    
    def _load_model(self):
        """Load FinBERT model and tokenizer"""
        self.logger.info(f"Loading FinBERT model: {self.model_name}")
        self.logger.info(f"Using device: {self.device}")
        
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        self.model = AutoModelForSequenceClassification.from_pretrained(self.model_name)
        self.model.to(self.device)
        self.model.eval()
        
        self.logger.info("FinBERT model loaded successfully")
    
    def analyze_text(self, text: str) -> Dict[str, Any]:
        """
        Analyze sentiment of a single text.
        
        Args:
            text: Text to analyze (headline or summary)
            
        Returns:
            Dict with sentiment label, score, and probabilities
        """
        if not self.model or not self.tokenizer:
            return {
                'label': 'neutral',
                'score': 0.5,
                'probabilities': {'positive': 0.33, 'negative': 0.33, 'neutral': 0.34}
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
                'label': 'neutral',
                'score': 0.5,
                'probabilities': {'positive': 0.33, 'negative': 0.33, 'neutral': 0.34}
            }
    
    def analyze_news_articles(self, articles: List[Dict[str, str]]) -> Dict[str, Any]:
        """
        Analyze sentiment across multiple news articles.
        
        Args:
            articles: List of news articles with 'headline' and 'summary' keys
            
        Returns:
            Dict with aggregate sentiment score (0-100) and article-level sentiments
        """
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
        return self.model is not None and self.tokenizer is not None

# FinBERT Sentiment Analysis Setup

## Overview

The stock market agent now includes **FinBERT** sentiment analysis to analyze financial news and enhance recommendations. FinBERT is a BERT-based model specifically trained on financial text for sentiment classification.

## Installation

### 1. Install Dependencies

```bash
pip install torch transformers sentencepiece
```

Or install all requirements:
```bash
pip install -r requirements.txt
```

### 2. First Run (Model Download)

The first time you run the application, FinBERT will automatically download (~500MB):

```bash
python web/app.py
```

You'll see:
```
Loading FinBERT model: ProsusAI/finbert
Using device: cpu
FinBERT model loaded successfully
```

**Note**: 
- Model downloads to `~/.cache/huggingface/`
- Takes 1-2 minutes on first run
- Subsequent runs are instant

## Hardware Requirements

### CPU (Recommended for Most Users)
- **RAM**: 4GB minimum, 8GB recommended
- **Storage**: 1GB for model files
- **Speed**: ~1-2 seconds per article

### GPU (Optional, Faster)
- **CUDA-compatible GPU** (NVIDIA)
- **Speed**: ~0.1-0.2 seconds per article
- Automatically detected and used if available

## How It Works

### Sentiment Scoring

FinBERT classifies text into 3 categories:
- **Positive**: Bullish sentiment (good news)
- **Negative**: Bearish sentiment (bad news)  
- **Neutral**: Mixed or neutral sentiment

### Integration with Recommendations

Sentiment is integrated as a **4th factor** in stock recommendations:

**Short-term (1 week):**
- Technical: 80%
- Sentiment: 20%

**Medium-term (3 months):**
- Fundamental: 50%
- Technical: 35%
- Sentiment: 15%

**Long-term (6-12 months):**
- Fundamental: 70%
- Technical: 15%
- Sentiment: 15%

### Sentiment Calculation

1. Fetches latest news articles (via Finnhub)
2. Analyzes each article's headline (70% weight) and summary (30% weight)
3. Aggregates sentiment across all articles
4. Converts to 0-100 score:
   - **0-40**: Negative sentiment
   - **40-60**: Neutral sentiment
   - **60-100**: Positive sentiment

## Usage Example

### In Code

```python
from src.tools.sentiment_analysis import SentimentAnalyzer

# Initialize analyzer (loads model on first call)
analyzer = SentimentAnalyzer()

# Analyze news articles
news_articles = [
    {'headline': 'Apple reports record Q4 earnings', 'summary': '...'},
    {'headline': 'iPhone sales exceed expectations', 'summary': '...'}
]

result = analyzer.analyze_news_articles(news_articles)
print(f"Overall Score: {result['overall_score']:.1f}/100")
print(f"Sentiment: {result['overall_sentiment']}")
print(f"Confidence: {result['confidence']:.1f}%")
```

### In Your App

Sentiment analysis is automatically integrated into stock recommendations. When you search for a stock, the system:

1. Fetches fundamental data
2. Fetches technical indicators
3. **Fetches and analyzes news (NEW)**
4. Combines all factors into final recommendation

## Performance Optimization

### Speed Up Initial Load

Pre-download the model:
```bash
python -c "from transformers import AutoTokenizer, AutoModelForSequenceClassification; AutoTokenizer.from_pretrained('ProsusAI/finbert'); AutoModelForSequenceClassification.from_pretrained('ProsusAI/finbert')"
```

### Reduce Memory Usage

If running on limited RAM, you can:
1. Use CPU mode (automatic if no GPU)
2. Process fewer news articles (default: 5)
3. Close other applications

### GPU Acceleration

If you have NVIDIA GPU with CUDA:
```bash
# Install PyTorch with CUDA support
pip install torch --index-url https://download.pytorch.org/whl/cu118
```

The system will automatically detect and use GPU.

## Troubleshooting

### Error: "Failed to load FinBERT model"

**Causes**:
- No internet connection (first download)
- Insufficient disk space
- Incompatible PyTorch version

**Solution**:
```bash
pip install --upgrade torch transformers
```

### Error: "RuntimeError: Couldn't load custom C++ ops"

**Solution**: Install sentencepiece:
```bash
pip install sentencepiece
```

### Slow Performance

**Solutions**:
1. **Reduce news articles**: Edit sentiment analyzer to process fewer items
2. **Use CPU efficiently**: Close other applications
3. **Upgrade to GPU**: Install CUDA-enabled PyTorch

### Model Not Downloading

**Solution**: Manual download:
```bash
python -c "from transformers import AutoTokenizer, AutoModelForSequenceClassification; AutoTokenizer.from_pretrained('ProsusAI/finbert'); AutoModelForSequenceClassification.from_pretrained('ProsusAI/finbert')"
```

## Alternative Models

If you want to try different models, edit `src/tools/sentiment_analysis.py`:

```python
# Default (recommended)
analyzer = SentimentAnalyzer("ProsusAI/finbert")

# Alternative: Tone analysis
analyzer = SentimentAnalyzer("yiyanghkust/finbert-tone")

# Alternative: General sentiment
analyzer = SentimentAnalyzer("nlptown/bert-base-multilingual-uncased-sentiment")
```

## Disabling Sentiment Analysis

If you want to disable sentiment (to save resources):

Edit `src/agent_improved.py` and set sentiment weight to 0, or simply don't install torch/transformers. The system will gracefully fall back to fundamental + technical only.

## Next Steps

1. Install dependencies: `pip install -r requirements.txt`
2. Start the app: `python web/app.py`
3. Wait for model download (first run only)
4. Test with a stock: Search for "AAPL" or "TSLA"
5. Check news sentiment in the analysis results

The sentiment score will appear in the recommendation summary and influence the final BUY/SELL/HOLD decision.

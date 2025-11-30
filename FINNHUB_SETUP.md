# Finnhub News Integration

## Overview

The stock market agent now uses **Finnhub** for fetching financial news instead of RSS feeds. Finnhub provides a more reliable news API with better metadata and filtering capabilities.

## Setup Instructions

### 1. Get a Free Finnhub API Key

1. Go to https://finnhub.io/register
2. Sign up for a free account
3. Navigate to your dashboard to get your API key
4. **Free tier includes**: 60 API calls/minute, company news, market news

### 2. Configure the API Key

Add your Finnhub API key to the `.env` file:

```bash
# Edit config/.env
FINNHUB_API_KEY=your_actual_api_key_here
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

The `requests` library (already in requirements.txt) is all you need for Finnhub.

### 4. Run the Application

```bash
# From the web directory
cd web
python app.py
```

Or from the root:
```bash
cd /Users/mayurmnankani/stockMarketAgent
python web/app.py
```

## Features

### Finnhub News vs RSS Feeds

| Feature | RSS Feeds | Finnhub API |
|---------|-----------|-------------|
| Reliability | ⚠️ Often breaks | ✅ Stable |
| Metadata | ❌ Limited | ✅ Rich (source, category, timestamp) |
| Rate Limits | None | 60/min (free) |
| Filtering | ❌ No | ✅ Date range, symbol |
| Sentiment | ❌ No | ✅ Available (paid) |
| Quality | ⚠️ Variable | ✅ Curated |

### API Usage

The `FinnhubNewsAgent` provides the same interface as the old `RSSNewsAgent`:

```python
from src.tools.finnhub_news import FinnhubNewsAgent

news_agent = FinnhubNewsAgent()
result = news_agent.fetch('AAPL', max_items=5, days_back=7)

if result.status == ResultStatus.SUCCESS:
    for article in result.data['news']:
        print(f"Headline: {article['headline']}")
        print(f"Source: {article['source']}")
        print(f"Date: {article['datetime']}")
        print(f"URL: {article['url']}")
```

### Response Format

Each news article includes:
- `headline`: Article title
- `summary`: Article summary (truncated to 300 chars)
- `url`: Link to full article
- `source`: News source (e.g., "Bloomberg", "Reuters")
- `datetime`: Publication date and time
- `category`: Article category (e.g., "company", "general")

## Rate Limits

**Free Tier**: 60 API calls/minute

For production usage with higher limits, consider upgrading to a paid plan at https://finnhub.io/pricing

## Troubleshooting

### Error: "Finnhub API key not configured"

**Solution**: Make sure you've added `FINNHUB_API_KEY` to `config/.env`:
```bash
FINNHUB_API_KEY=your_key_here
```

### Error: "HTTP 429 Too Many Requests"

**Solution**: You've exceeded the 60 calls/minute free tier limit. Wait a minute or upgrade your plan.

### No news returned

**Possible causes**:
1. Invalid ticker symbol
2. No news published in the date range (try increasing `days_back`)
3. API key quota exceeded

## Migration Notes

### Changes Made

1. ✅ Created `src/tools/finnhub_news.py` - New Finnhub news agent
2. ✅ Updated `web/repositories/stock_repository.py` - Switched to `FinnhubNewsAgent`
3. ✅ Updated `requirements.txt` - Removed `feedparser` dependency
4. ✅ Updated `config/.env` - Added `FINNHUB_API_KEY` placeholder
5. ✅ Updated `web/config.py` - Added dotenv loading

### Backward Compatibility

The new `FinnhubNewsAgent` maintains the same interface as `RSSNewsAgent`, so no changes are needed in:
- `src/agent.py` or `src/agent_improved.py`
- `web/services/*`
- `web/routes/*`

The only requirement is setting up the Finnhub API key.

## Next Steps

Once you have your API key configured, the news functionality will work automatically. The agent will fetch the latest news articles when analyzing stocks.

**Test it**:
```bash
# Start the app
python web/app.py

# Visit http://127.0.0.1:5001
# Search for a stock like "AAPL"
# Check the news section in the analysis
```

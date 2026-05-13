"""
Stock Analysis Service
Business logic for stock analysis operations
"""

import re
from typing import Dict, Any, Optional, List
from repositories.stock_repository import IStockRepository
from application.use_cases.run_stock_analysis import StockAnalysisUseCase
from adapters.market_data.yahoo_finance_adapter import YahooFinanceAdapter
from adapters.market_data.yahoo_finance_screener_adapter import YahooFinanceScreenerAdapter
from adapters.news.finnhub_adapter import FinnhubNewsAdapter
from adapters.sentiment.finbert_adapter import FinbertSentimentAdapter
from adapters.company_lookup.yahoo_company_lookup_adapter import YahooCompanyLookupAdapter
from models import StockAnalysis, CompanyMatch
from core.models.market import MarketOverview


class StockAnalysisService:
    """
    Coordinates stock analysis operations
    Implements business logic for stock queries
    """
    
    def __init__(self, repository: IStockRepository):
        self.repository = repository
        # Instantiate adapters for unified use-case (temporary duplication until full migration)
        market = getattr(repository, 'market_data', YahooFinanceAdapter())
        news = getattr(repository, 'news_adapter', FinnhubNewsAdapter())
        company_lookup = getattr(repository, 'company_lookup', YahooCompanyLookupAdapter())
        sentiment = FinbertSentimentAdapter()
        self.screener = YahooFinanceScreenerAdapter()  # Market screener adapter
        self.use_case = StockAnalysisUseCase(
            market_data=market,
            news_adapter=news,
            sentiment_adapter=sentiment,
            company_lookup=company_lookup,
        )
    
    def find_ticker(self, query: str) -> Optional[CompanyMatch]:
        """
        Find ticker from query - tries ticker validation first, then company search
        
        Args:
            query: User's search query (could be ticker or company name)
            
        Returns:
            CompanyMatch if found, None otherwise
        """
        print(f"[DEBUG] find_ticker called with: '{query}'")
        
        # Try to extract and validate ticker tokens
        ticker_match = self._try_ticker_tokens(query)
        if ticker_match:
            print(f"[DEBUG] Ticker match found: {ticker_match}")
            return ticker_match
        
        # Fall back to company search
        print(f"[DEBUG] No ticker match, falling back to company search")
        company_match = self._search_company(query)
        print(f"[DEBUG] Company search result: {company_match}")
        return company_match
    
    def _try_ticker_tokens(self, query: str) -> Optional[CompanyMatch]:
        """Try to find valid ticker in query string"""
        try:
            def _is_valid_quote(raw_quote: Dict[str, Any]) -> bool:
                """Determine if a wrapped quote response is genuinely valid."""
                if not isinstance(raw_quote, dict):
                    return False
                data = raw_quote.get('data')  # yahoo_agent.handle wraps result in {'status':'ok','data':{}}
                if not isinstance(data, dict):
                    return False
                # Reject if explicit error field inside data
                if data.get('error'):
                    return False
                # Require a non-null price (regularMarketPrice/currentPrice mapping)
                price = data.get('price')
                if price is None:
                    return False
                # Basic symbol sanity (1-5 uppercase letters/numbers or caret index)
                symbol = data.get('symbol') or ''
                if symbol.startswith('^'):
                    return True
                if 1 <= len(symbol) <= 5 and symbol.upper() == symbol:
                    return True
                return False

            # First check if the entire query looks like a ticker
            original_query = query.strip()
            normalized_query = original_query.upper()
            
            # Only try as direct ticker if:
            # 1. Starts with ^ (index), OR
            # 2. Is 1-5 chars AND original query is already uppercase (likely typed as ticker)
            # 3. Is 1-5 chars AND contains numbers/dots/hyphens (e.g., BRK.B, M1)
            is_ticker_like = (
                normalized_query.startswith('^') or 
                (len(normalized_query) <= 5 and original_query.isupper()) or
                (len(normalized_query) <= 5 and any(c in original_query for c in '.0123456789-'))
            )
            
            if is_ticker_like:
                # Try validating as a ticker
                quote_result = self.repository.get_quote(normalized_query)
                if _is_valid_quote(quote_result):
                    data = quote_result['data']
                    longname = data.get('name') or data.get('shortName') or data.get('longName') or data.get('symbol') or normalized_query
                    return CompanyMatch(
                        symbol=data.get('symbol', normalized_query),
                        long_name=longname,
                        short_name=data.get('shortName')
                    )
            
            # Common English words that happen to be valid tickers — never treat these as tickers
            # when they appear inside a sentence (multi-word query).
            _ENGLISH_STOPWORDS = {
                'A', 'I', 'IS', 'IT', 'IN', 'ON', 'AT', 'TO', 'DO', 'GO',
                'BE', 'BY', 'MY', 'AN', 'OR', 'OF', 'AS', 'SO', 'IF', 'NO',
                'UP', 'US', 'WE', 'HE', 'ME', 'AM', 'PM', 'VS', 'RE',
                'THE', 'FOR', 'AND', 'NOT', 'ARE', 'ALL', 'CAN', 'HAS',
                'ITS', 'WAS', 'HAD', 'DID', 'GET', 'GOT', 'BUY', 'NOW',
                'NEW', 'TOP', 'LOW', 'HOW', 'WHY', 'WHO', 'THIS', 'THAT',
                'GOOD', 'BEST', 'SELL', 'HOLD', 'TIME', 'WILL', 'BEEN',
            }

            # Extract candidate tokens (caret-prefixed or alphanumeric)
            candidates = re.findall(r"\b[\^A-Za-z0-9\.\-]{1,6}\b", query)
            
            for token in candidates:
                token = token.strip()
                if not token:
                    continue
                
                # Normalize to uppercase for validation
                if token.startswith('^'):
                    cand = token
                else:
                    if token.isalpha() or token.isalnum():
                        cand = token.upper()
                    else:
                        continue

                # Skip common English words — they are valid tickers but almost never intended
                if cand in _ENGLISH_STOPWORDS:
                    continue
                
                # Validate ticker
                quote_result = self.repository.get_quote(cand)
                if _is_valid_quote(quote_result):
                    data = quote_result['data']
                    longname = data.get('name') or data.get('shortName') or data.get('longName') or data.get('symbol') or cand
                    return CompanyMatch(
                        symbol=data.get('symbol', cand),
                        long_name=longname,
                        short_name=data.get('shortName')
                    )
        except Exception as e:
            print(f"Error in ticker validation: {e}")
        
        return None
    
    def _search_company(self, query: str) -> Optional[CompanyMatch]:
        """Search for company by name"""
        print(f"[DEBUG] Searching company for query: {query}")
        match = self.repository.search_company(query)
        print(f"[DEBUG] Company search returned: {match}")
        if not match:
            return None
        
        return CompanyMatch(
            symbol=match['symbol'],
            long_name=match.get('long_name'),
            short_name=match.get('short_name')
        )
    
    def get_analysis(self, ticker: str, company_name: str) -> StockAnalysis:
        """Get complete stock analysis (now leveraging unified use-case)."""
        unified = self.use_case.run(ticker)
        # Fallback if error
        if unified.get('error'):
            quote = self.repository.get_quote(ticker)
            recommendations = self.repository.get_recommendations(ticker)
            news = self.repository.get_news(ticker)
            price_history = self.repository.get_price_history(ticker, period='1mo')
            return StockAnalysis(
                ticker=ticker,
                company_name=company_name,
                quote=quote,
                recommendations=recommendations,
                news=news,
                price_history=price_history
            )
        # Preserve original shape but embed unified recommendation report under recommendations['unified']
        quote = unified.get('quote') or self.repository.get_quote(ticker)
        legacy = unified.get('legacy_components', {})
        rec_report = unified.get('recommendation_report')
        # ------------------------------------------------------------------
        # Restore legacy horizon keys (short_term, medium_term, long_term)
        # for formatting layer which still expects them. If the legacy
        # agent output already provided them, reuse directly. Otherwise,
        # derive them from unified_report horizons + legacy component
        # summaries to avoid "N/A" display regression.
        # ------------------------------------------------------------------
        short_term = legacy.get('short_term')
        medium_term = legacy.get('medium_term')
        long_term = legacy.get('long_term')

        try:
            if not (short_term and medium_term and long_term) and isinstance(rec_report, dict):
                horizons = rec_report.get('horizons', {})
                fundamental = legacy.get('fundamental', {})
                technical = legacy.get('technical', {})
                sentiment = legacy.get('sentiment', {})

                # Helper to map rating/score -> legacy styled label
                def _label(rating: str, score: float) -> str:
                    rating = (rating or '').lower()
                    if rating == 'buy':
                        return 'STRONG BUY' if score >= 70 else 'BUY'
                    if rating == 'sell':
                        return 'STRONG SELL' if score < 30 else 'SELL'
                    return 'HOLD'

                # Confidence weighting mirroring original agent logic
                f_conf = fundamental.get('confidence', 0) or 0
                t_conf = technical.get('confidence', 0) or 0
                s_conf = sentiment.get('confidence', 0) or 0

                # Build summaries with prefixed segments so formatting_service can split them
                def _reason_items(summary: str) -> list[str]:
                    text = (summary or '').strip()
                    if not text:
                        return []
                    return [item.strip() for item in text.split(',') if item.strip()]

                def _select_horizon_items(section: str, horizon: str, summary: str) -> str:
                    items = _reason_items(summary)
                    if not items:
                        return ''

                    if section == 'fundamental' and horizon == 'medium':
                        return ', '.join(items[:2])

                    if section == 'fundamental' and horizon == 'long':
                        quality_terms = ('debt', 'liquidity', 'margin', 'roe', 'book value', 'current ratio')
                        quality_items = [item for item in items if any(term in item.lower() for term in quality_terms)]
                        chosen = quality_items[:2] or items[-2:]
                        return ', '.join(chosen)

                    if section == 'technical' and horizon == 'medium':
                        medium_terms = ('macd', 'rsi', 'adx', 'sma20', 'sma50', 'stochastic', 'mfi')
                        medium_items = [item for item in items if any(term in item.lower() for term in medium_terms)]
                        chosen = medium_items[:2] or items[:2]
                        return ', '.join(chosen)

                    if section == 'technical' and horizon == 'long':
                        long_terms = ('sma200', 'golden cross', 'major golden cross', 'long-term uptrend', 'long-term downtrend')
                        long_items = [item for item in items if any(term in item.lower() for term in long_terms)]
                        return ', '.join(long_items[:2])

                    if section == 'sentiment' and horizon == 'medium':
                        return ', '.join(items[:1])

                    return ', '.join(items)

                def _horizon_reason(section: str, horizon: str, summary: str) -> str:
                    text = _select_horizon_items(section, horizon, summary)
                    if not text:
                        return ''

                    if section == 'technical' and horizon == 'short':
                        return f"Near-term momentum setup: {text}"
                    if section == 'sentiment' and horizon == 'short':
                        return f"News-driven catalyst bias (1-4 weeks): {text}"

                    if section == 'fundamental' and horizon == 'medium':
                        return f"Fundamental setup for the next quarter: {text}"
                    if section == 'technical' and horizon == 'medium':
                        return f"Trend confirmation over the next few months: {text}"
                    if section == 'sentiment' and horizon == 'medium':
                        return f"Sentiment tailwind/headwind for medium term: {text}"

                    if section == 'fundamental' and horizon == 'long':
                        return f"Long-horizon business quality and valuation: {text}"
                    if section == 'technical' and horizon == 'long':
                        return f"Primary trend structure for 6-12 months: {text}"

                    return text

                def _short_summary():
                    parts = []
                    tech = _horizon_reason('technical', 'short', technical.get('summary', ''))
                    sent = _horizon_reason('sentiment', 'short', sentiment.get('summary', ''))
                    if tech: parts.append(f"Technical: {tech}")
                    if sent: parts.append(f"Sentiment: {sent}")
                    return ' | '.join(parts)

                def _medium_summary():
                    parts = []
                    fund = _horizon_reason('fundamental', 'medium', fundamental.get('summary', ''))
                    tech = _horizon_reason('technical', 'medium', technical.get('summary', ''))
                    sent = _horizon_reason('sentiment', 'medium', sentiment.get('summary', ''))
                    if fund: parts.append(f"Fundamentals: {fund}")
                    if tech: parts.append(f"Technical: {tech}")
                    if sent: parts.append(f"Sentiment: {sent}")
                    return ' | '.join(parts)

                def _long_summary():
                    parts = []
                    fund = _horizon_reason('fundamental', 'long', fundamental.get('summary', ''))
                    tech = _horizon_reason('technical', 'long', technical.get('summary', ''))
                    if fund: parts.append(f"Fundamentals: {fund}")
                    if tech: parts.append(f"Technical: {tech}")
                    return ' | '.join(parts)

                # Short horizon
                if horizons.get('short'):
                    h = horizons['short']
                    short_term = {
                        'label': _label(h.get('rating'), h.get('score', 0)),
                        'summary': _short_summary(),
                        'score': h.get('score'),
                        'confidence': round(t_conf * 0.8 + s_conf * 0.2, 1)
                    }
                # Medium horizon
                if horizons.get('medium'):
                    h = horizons['medium']
                    medium_term = {
                        'label': _label(h.get('rating'), h.get('score', 0)),
                        'summary': _medium_summary(),
                        'score': h.get('score'),
                        'confidence': round(f_conf * 0.55 + t_conf * 0.35 + s_conf * 0.10, 1)
                    }
                # Long horizon
                if horizons.get('long'):
                    h = horizons['long']
                    long_term = {
                        'label': _label(h.get('rating'), h.get('score', 0)),
                        'summary': _long_summary(),
                        'score': h.get('score'),
                        'confidence': round(f_conf * 0.8 + t_conf * 0.2, 1)
                    }
        except Exception as e:
            print(f"[WARN] Failed to derive legacy horizons from unified report: {e}")

        # Assemble recommendations dict: keep legacy pieces + new report
        recommendations = {
            'fundamental': legacy.get('fundamental'),
            'technical': legacy.get('technical'),
            'sentiment': legacy.get('sentiment'),
            'unified_report': rec_report,
            # Restored horizon keys for UI consumption
            'short_term': short_term,
            'medium_term': medium_term,
            'long_term': long_term,
        }
        news = self.repository.get_news(ticker)
        price_history = self.repository.get_price_history(ticker, period='1mo')
        return StockAnalysis(
            ticker=ticker,
            company_name=company_name,
            quote=quote,
            recommendations=recommendations,
            news=news,
            price_history=price_history
        )
    
    def get_earnings(self, ticker: str) -> Dict[str, Any]:
        """Get earnings data for ticker"""
        return self.repository.get_earnings(ticker)
    
    def get_stock_info(self, ticker: str) -> Dict[str, Any]:
        """Get comprehensive stock info"""
        return self.repository.get_stock_info(ticker)
    
    def get_market_overview(self) -> MarketOverview:
        """
        Fetch market-wide overview (top movers, gainers, losers, most active, indices).
        
        Returns:
            MarketOverview with all sections (fails open with empty lists on errors)
        """
        try:
            return self.screener.get_market_overview()
        except Exception as e:
            print(f"[WARN] Error fetching market overview: {e}")
            # Return empty overview on failure to prevent crash
            return MarketOverview(
                movers=[],
                gainers=[],
                losers=[],
                most_active=[],
                indices=[],
            )

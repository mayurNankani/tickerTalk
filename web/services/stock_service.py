"""
Stock Analysis Service
Business logic for stock analysis operations
"""

import re
from typing import Dict, Any, Optional, List
from repositories.stock_repository import IStockRepository
from models import StockAnalysis, CompanyMatch


class StockAnalysisService:
    """
    Coordinates stock analysis operations
    Implements business logic for stock queries
    """
    
    def __init__(self, repository: IStockRepository):
        self.repository = repository
    
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
        """
        Get complete stock analysis
        
        Args:
            ticker: Stock ticker symbol
            company_name: Company display name
            
        Returns:
            Complete StockAnalysis object
        """
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
    
    def get_earnings(self, ticker: str) -> Dict[str, Any]:
        """Get earnings data for ticker"""
        return self.repository.get_earnings(ticker)
    
    def get_stock_info(self, ticker: str) -> Dict[str, Any]:
        """Get comprehensive stock info"""
        return self.repository.get_stock_info(ticker)

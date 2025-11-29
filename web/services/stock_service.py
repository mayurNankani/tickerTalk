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
        # Try to extract and validate ticker tokens
        ticker_match = self._try_ticker_tokens(query)
        if ticker_match:
            return ticker_match
        
        # Fall back to company search
        return self._search_company(query)
    
    def _try_ticker_tokens(self, query: str) -> Optional[CompanyMatch]:
        """Try to find valid ticker in query string"""
        try:
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
                if isinstance(quote_result, dict) and quote_result.get('status') == 'ok':
                    data = quote_result.get('data', {})
                    longname = data.get('name') or data.get('shortName') or data.get('longName') or cand
                    
                    return CompanyMatch(
                        symbol=cand,
                        long_name=longname,
                        short_name=data.get('shortName')
                    )
        except Exception as e:
            print(f"Error in ticker validation: {e}")
        
        return None
    
    def _search_company(self, query: str) -> Optional[CompanyMatch]:
        """Search for company by name"""
        match = self.repository.search_company(query)
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

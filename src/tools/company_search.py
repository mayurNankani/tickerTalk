"""
Company Search Tool
Searches for company ticker symbols and information using Yahoo Finance.
"""

from typing import Dict, Any, List, Optional
from yahooquery import search as yq_search
from .base import AnalysisTool, ToolResult, ResultStatus


class CompanySearch(AnalysisTool):
    """Searches for company information and ticker symbols"""
    
    def analyze(self, company_name: str, **kwargs) -> ToolResult:
        """
        Search for company ticker symbols based on company name.
        
        Args:
            company_name: The name of the company to search for
            **kwargs: Additional parameters (currently unused)
            
        Returns:
            ToolResult containing matches
        """
        if not company_name or not isinstance(company_name, str):
            return ToolResult(
                status=ResultStatus.ERROR,
                error="Invalid company name"
            )
        
        try:
            company_name = company_name.strip()
            
            # Use yahooquery to search for the company
            search_results = yq_search(company_name)
            
            # Filter for equity matches
            matches = self._filter_equity_matches(search_results)
            
            if not matches:
                return ToolResult(
                    status=ResultStatus.NO_DATA,
                    data={'query': company_name, 'matches': [], 'count': 0},
                    error=f"No equity matches found for '{company_name}'"
                )
            
            return ToolResult(
                status=ResultStatus.SUCCESS,
                data={
                    'query': company_name,
                    'matches': matches,
                    'count': len(matches)
                },
                metadata={'source': 'yahooquery'}
            )
            
        except Exception as e:
            self.logger.error(f"Error searching for '{company_name}': {e}", exc_info=True)
            return ToolResult(
                status=ResultStatus.ERROR,
                error=f"Search failed: {str(e)}",
                data={'query': company_name, 'matches': [], 'count': 0}
            )
    
    def _filter_equity_matches(self, search_results: Dict) -> List[Dict[str, Any]]:
        """Filter search results for equity matches only"""
        matches = []
        for result in search_results.get('quotes', []):
            if result.get('quoteType') == 'EQUITY':
                matches.append({
                    'symbol': result.get('symbol'),
                    'long_name': result.get('longname'),
                    'short_name': result.get('shortname'),
                    'exchange': result.get('exchange'),
                    'quote_type': result.get('quoteType')
                })
        return matches
    
    def get_best_match(self, company_name: str) -> Optional[str]:
        """
        Get the most likely ticker symbol for a company name.
        
        Args:
            company_name: The name of the company
            
        Returns:
            The most likely ticker symbol, or None if no match found
        """
        result = self.analyze(company_name)
        
        if result.is_success() and result.data and result.data.get("matches"):
            return result.data["matches"][0]["symbol"]
        
        return None
    
    def search(self, company_name: str) -> Dict[str, Any]:
        """
        Legacy method for backward compatibility.
        Returns dict directly instead of ToolResult.
        """
        result = self.analyze(company_name)
        if result.data:
            return result.data
        return {
            'query': company_name,
            'matches': [],
            'count': 0,
            'error': result.error
        }

from typing import Dict, Any
import yfinance as yf
from yahooquery import search
from .base import AnalysisTool

class CompanySearch(AnalysisTool):
    def analyze(self, company_name: str) -> Dict[str, Any]:
        """
        Search for company ticker symbols based on company name.
        
        Args:
            company_name (str): The name of the company to search for
            
        Returns:
            Dict[str, Any]: Search results including possible matches
        """
        try:
            # Use yahooquery to search for the company
            search_results = search(company_name)
            # print(f"Debug - Search results: {search_results}")

            matches = []
            for result in search_results.get('quotes', []):
                if result.get('quoteType') == 'EQUITY':  # Only include stocks
                    matches.append({
                        'symbol': result.get('symbol'),
                        'long_name': result.get('longname'),
                        'short_name': result.get('shortname'),
                        'exchange': result.get('exchange'),
                        'quote_type': result.get('quoteType')
                    })
            
            return {
                "query": company_name,
                "matches": matches,
                "count": len(matches)
            }
            
        except Exception as e:
            print(f"Debug - Error occurred: {str(e)}")
            import traceback
            print(f"Debug - Full traceback: {traceback.format_exc()}")
            return {
                "error": str(e),
                "query": company_name,
                "matches": [],
                "count": 0
            }
    
    def get_best_match(self, company_name: str) -> str:
        """
        Get the most likely ticker symbol for a company name.
        
        Args:
            company_name (str): The name of the company
            
        Returns:
            str: The most likely ticker symbol, or None if no match found
        """
        results = self.analyze(company_name)
        
        if results.get("matches"):
            # Return the first match as it's typically the most relevant
            return results["matches"][0]["symbol"]
        
        return None
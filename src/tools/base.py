from abc import ABC, abstractmethod
from typing import Dict, Any

class AnalysisTool(ABC):
    """Base interface for stock analysis tools."""
    
    @abstractmethod
    def analyze(self, ticker: str) -> Dict[str, Any]:
        """
        Analyze a stock and return the results.
        
        Args:
            ticker (str): The stock ticker symbol
            
        Returns:
            Dict[str, Any]: Analysis results
        """
        pass
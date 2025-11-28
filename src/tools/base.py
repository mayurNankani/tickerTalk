"""
Base classes and utilities for stock market analysis tools.
Provides consistent interfaces, error handling, and result formatting.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, TypedDict
from dataclasses import dataclass
from enum import Enum
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ResultStatus(Enum):
    """Standard result statuses for tool operations"""
    SUCCESS = "success"
    ERROR = "error"
    PARTIAL = "partial"
    NO_DATA = "no_data"


@dataclass
class ToolResult:
    """
    Standardized result wrapper for all analysis tools.
    
    Attributes:
        status: Operation status (success, error, partial, no_data)
        data: The actual result data (None if error)
        error: Error message if status is ERROR
        metadata: Additional context about the operation
    """
    status: ResultStatus
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def is_success(self) -> bool:
        """Check if the operation was successful"""
        return self.status == ResultStatus.SUCCESS
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'status': self.status.value,
            'data': self.data,
            'error': self.error,
            'metadata': self.metadata
        }


class AnalysisTool(ABC):
    """
    Base interface for stock analysis tools.
    All analysis tools should inherit from this class.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
    
    @abstractmethod
    def analyze(self, ticker: str, **kwargs) -> ToolResult:
        """
        Analyze a stock and return standardized results.
        
        Args:
            ticker: The stock ticker symbol
            **kwargs: Additional tool-specific parameters
            
        Returns:
            ToolResult: Standardized result object
        """
        pass
    
    def _handle_error(self, error: Exception, ticker: str) -> ToolResult:
        """
        Standardized error handling for all tools.
        
        Args:
            error: The exception that occurred
            ticker: The ticker being analyzed
            
        Returns:
            ToolResult with error status
        """
        error_msg = f"Error analyzing {ticker}: {str(error)}"
        self.logger.error(error_msg, exc_info=True)
        return ToolResult(
            status=ResultStatus.ERROR,
            error=error_msg,
            metadata={'ticker': ticker, 'error_type': type(error).__name__}
        )
    
    def _validate_ticker(self, ticker: str) -> bool:
        """
        Validate ticker symbol format.
        
        Args:
            ticker: The ticker to validate
            
        Returns:
            True if valid, False otherwise
        """
        if not ticker or not isinstance(ticker, str):
            return False
        # Basic validation: 1-5 uppercase letters/numbers
        ticker = ticker.strip().upper()
        return 1 <= len(ticker) <= 5 and ticker.replace('.', '').replace('-', '').isalnum()


class DataFetcher(ABC):
    """Base class for tools that fetch external data (news, web search, etc.)"""
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
    
    @abstractmethod
    def fetch(self, query: str, **kwargs) -> ToolResult:
        """
        Fetch data based on a query.
        
        Args:
            query: The search query
            **kwargs: Additional fetcher-specific parameters
            
        Returns:
            ToolResult: Standardized result object
        """
        pass
    
    def _get_default_headers(self) -> Dict[str, str]:
        """Get standard browser-like headers for HTTP requests"""
        return {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
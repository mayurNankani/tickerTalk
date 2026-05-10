"""Protocol for accessing market data (quotes & historical prices)."""
from typing import Protocol
from core.models import StockQuote, PriceHistory

class MarketDataAdapter(Protocol):
    def get_quote(self, symbol: str) -> StockQuote: ...
    def get_price_history(self, symbol: str, period: str = "1mo") -> PriceHistory: ...

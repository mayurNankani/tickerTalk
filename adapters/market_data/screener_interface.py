"""Protocol for accessing market screener data (top movers, indices, etc.)."""
from typing import Protocol
from core.models.market import MarketOverview


class MarketScreenerAdapter(Protocol):
    """Protocol for market-wide screener data (not single-stock quotes)."""
    
    def get_market_overview(self) -> MarketOverview:
        """
        Fetch a comprehensive market overview snapshot.
        
        Returns:
            MarketOverview containing movers, gainers, losers, most active, and indices.
        
        Raises:
            Exception on network or parsing errors (caller handles gracefully).
        """
        ...

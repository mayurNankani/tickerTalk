"""Simple thread-safe in-memory TTL cache.

Used to avoid redundant HTTP calls to yfinance and Finnhub within a short
window (default 300 s). Not suitable for multi-process deployments — use
Redis in that case.
"""
from __future__ import annotations
import time
import threading
from typing import Any, Dict, Optional, Tuple


class TTLCache:
    """Lightweight in-process key/value cache with per-entry TTL."""

    def __init__(self, default_ttl: int = 300) -> None:
        self._store: Dict[str, Tuple[Any, float]] = {}
        self._lock = threading.Lock()
        self.default_ttl = default_ttl

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            value, expires_at = entry
            if time.monotonic() > expires_at:
                del self._store[key]
                return None
            return value

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        ttl = ttl if ttl is not None else self.default_ttl
        with self._lock:
            self._store[key] = (value, time.monotonic() + ttl)

    def delete(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._store)


# Module-level singletons — shared across all requests in the same process
quote_cache = TTLCache(default_ttl=300)   # 5 min — intraday prices
news_cache = TTLCache(default_ttl=600)    # 10 min — news changes less often
history_cache = TTLCache(default_ttl=180) # 3 min — price history (chart)
analysis_cache = TTLCache(default_ttl=600) # 10 min — formatted analysis HTML + news articles

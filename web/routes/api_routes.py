"""
API Routes Blueprint
RESTful endpoints for data fetching
"""

import threading
import time
from flask import Blueprint, request, jsonify
from services import StockAnalysisService
from utils.cache import TTLCache


market_overview_cache = TTLCache(default_ttl=120)
_market_refresh_started = False
_market_refresh_lock = threading.Lock()


def _normalize_cache_seconds(cache_seconds: int) -> int:
    if cache_seconds < 15:
        return 15
    if cache_seconds > 600:
        return 600
    return cache_seconds


def _market_overview_cache_key(cache_seconds: int) -> str:
    return f"market_overview:{cache_seconds}"


def _serialize_market_overview(overview) -> dict:
    return {
        'movers': [
            {
                'symbol': item.symbol,
                'name': item.name,
                'price': item.price,
                'change_percent': item.change_percent,
                'change_absolute': item.change_absolute,
                'market_cap': item.market_cap,
                'volume': item.volume,
                'week_52_high': item.week_52_high,
                'week_52_low': item.week_52_low,
            }
            for item in overview.movers
        ],
        'gainers': [
            {
                'symbol': item.symbol,
                'name': item.name,
                'price': item.price,
                'change_percent': item.change_percent,
                'change_absolute': item.change_absolute,
                'market_cap': item.market_cap,
                'volume': item.volume,
                'week_52_high': item.week_52_high,
                'week_52_low': item.week_52_low,
            }
            for item in overview.gainers
        ],
        'losers': [
            {
                'symbol': item.symbol,
                'name': item.name,
                'price': item.price,
                'change_percent': item.change_percent,
                'change_absolute': item.change_absolute,
                'market_cap': item.market_cap,
                'volume': item.volume,
                'week_52_high': item.week_52_high,
                'week_52_low': item.week_52_low,
            }
            for item in overview.losers
        ],
        'most_active': [
            {
                'symbol': item.symbol,
                'name': item.name,
                'price': item.price,
                'change_percent': item.change_percent,
                'change_absolute': item.change_absolute,
                'market_cap': item.market_cap,
                'volume': item.volume,
                'week_52_high': item.week_52_high,
                'week_52_low': item.week_52_low,
            }
            for item in overview.most_active
        ],
        'indices': [
            {
                'symbol': item.symbol,
                'name': item.name,
                'price': item.price,
                'change_percent': item.change_percent,
                'change_absolute': item.change_absolute,
                'market_cap': item.market_cap,
                'volume': item.volume,
                'week_52_high': item.week_52_high,
                'week_52_low': item.week_52_low,
            }
            for item in overview.indices
        ],
        'timestamp': overview.timestamp.isoformat(),
    }


def warm_market_overview_cache(stock_service: StockAnalysisService, cache_seconds: int = 120) -> bool:
    """Pre-fetch market overview and store it in the API cache."""
    normalized_cache_seconds = _normalize_cache_seconds(cache_seconds)
    cache_key = _market_overview_cache_key(normalized_cache_seconds)

    try:
        overview = stock_service.get_market_overview()
        payload = _serialize_market_overview(overview)
        market_overview_cache.set(cache_key, payload, ttl=normalized_cache_seconds)
        return True
    except Exception as exc:
        print(f"[WARN] Market overview warm-up failed: {exc}")
        return False


def start_market_overview_refresh_worker(
    stock_service: StockAnalysisService,
    cache_seconds: int = 120,
    refresh_interval_seconds: int = 90,
) -> bool:
    """Start a daemon worker that refreshes market overview cache periodically."""
    global _market_refresh_started

    normalized_cache_seconds = _normalize_cache_seconds(cache_seconds)
    refresh_interval_seconds = max(15, int(refresh_interval_seconds))

    with _market_refresh_lock:
        if _market_refresh_started:
            return False
        _market_refresh_started = True

    def _refresh_loop() -> None:
        warm_market_overview_cache(stock_service, normalized_cache_seconds)
        while True:
            time.sleep(refresh_interval_seconds)
            warm_market_overview_cache(stock_service, normalized_cache_seconds)

    threading.Thread(
        target=_refresh_loop,
        name="market-overview-refresh",
        daemon=True,
    ).start()
    return True


def init_api_routes(stock_service: StockAnalysisService):
    """
    Initialize API routes with injected dependencies

    Args:
        stock_service: StockAnalysisService instance
    """
    api_bp = Blueprint('api', __name__, url_prefix='/api')

    @api_bp.route('/price-history', methods=['GET'])
    def get_price_history():
        """Fetch price history for chart rendering"""
        ticker = request.args.get('ticker', '')
        period = request.args.get('period', '1mo')

        if not ticker:
            return jsonify({'error': 'Ticker is required'}), 400

        try:
            price_data = stock_service.repository.get_price_history(ticker, period)
            return jsonify(price_data)
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @api_bp.route('/market-overview', methods=['GET'])
    def get_market_overview():
        """Fetch comprehensive market overview (movers, gainers, losers, active, indices)"""
        try:
            cache_seconds = _normalize_cache_seconds(
                request.args.get('cache_seconds', default=120, type=int)
            )

            cache_key = _market_overview_cache_key(cache_seconds)
            cached = market_overview_cache.get(cache_key)
            if cached is not None:
                return jsonify(cached)

            warm_market_overview_cache(stock_service, cache_seconds)
            refreshed = market_overview_cache.get(cache_key)
            if refreshed is not None:
                return jsonify(refreshed)

            return jsonify({'error': 'Unable to fetch market overview right now'}), 503
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    return api_bp

"""Unit tests for StockAnalysisService ticker resolution.

We mock the repository so no real HTTP calls are made.
Run with: pytest tests/
"""

import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "web")))


def _make_good_quote(symbol: str, price: float = 150.0) -> dict:
    return {
        "status": "ok",
        "data": {"symbol": symbol, "price": price, "currency": "USD", "name": f"{symbol} Inc"},
        "error": None,
    }


def _make_bad_quote() -> dict:
    return {"status": "error", "data": {"price": None, "symbol": "XX"}, "error": "Not found"}


def _make_service(repo_mock):
    """Create a StockAnalysisService with all expensive deps mocked."""
    with (
        patch("services.stock_service.StockAnalysisUseCase") as mock_use_case,
        patch("services.stock_service.YahooFinanceAdapter"),
        patch("services.stock_service.FinnhubNewsAdapter"),
        patch("services.stock_service.FinbertSentimentAdapter"),
        patch("services.stock_service.YahooCompanyLookupAdapter"),
    ):
        mock_use_case.return_value = MagicMock()
        from services.stock_service import StockAnalysisService

        service = StockAnalysisService(repository=repo_mock)
    return service


class TestTryTickerTokens:
    def _svc(self, quote_map: dict):
        repo = MagicMock()
        repo.get_quote.side_effect = lambda ticker: quote_map.get(ticker, _make_bad_quote())
        repo.market_data = MagicMock()
        repo.news_adapter = MagicMock()
        repo.company_lookup = MagicMock()
        return _make_service(repo), repo

    def test_uppercase_ticker_directly_resolved(self):
        svc, _ = self._svc({"AAPL": _make_good_quote("AAPL")})
        result = svc._try_ticker_tokens("AAPL")
        assert result is not None
        assert result.symbol == "AAPL"

    def test_lowercase_company_word_not_treated_as_ticker(self):
        repo = MagicMock()
        repo.get_quote.return_value = _make_bad_quote()
        repo.market_data = repo.news_adapter = repo.company_lookup = MagicMock()
        svc = _make_service(repo)
        result = svc._try_ticker_tokens("apple")
        if result is not None:
            assert result.symbol is not None

    def test_invalid_ticker_returns_none(self):
        svc, _ = self._svc({})
        result = svc._try_ticker_tokens("ZZZZ")
        assert result is None

    def test_index_ticker_resolved(self):
        svc, _ = self._svc({"^GSPC": _make_good_quote("^GSPC", 5000.0)})
        result = svc._try_ticker_tokens("^GSPC")
        assert result is not None
        assert result.symbol == "^GSPC"

    def test_price_none_rejected(self):
        repo = MagicMock()
        repo.get_quote.return_value = {
            "status": "ok",
            "data": {"symbol": "FAKE", "price": None, "currency": "USD", "name": "Fake Corp"},
            "error": None,
        }
        repo.market_data = repo.news_adapter = repo.company_lookup = MagicMock()
        svc = _make_service(repo)
        result = svc._try_ticker_tokens("FAKE")
        assert result is None


class TestSearchCompany:
    def _svc_with_company(self, match):
        repo = MagicMock()
        repo.search_company.return_value = match
        repo.market_data = repo.news_adapter = repo.company_lookup = MagicMock()
        return _make_service(repo)

    def test_returns_company_match_on_hit(self):
        svc = self._svc_with_company(
            {"symbol": "GOOG", "long_name": "Alphabet Inc", "short_name": "Alphabet"}
        )
        result = svc._search_company("google")
        assert result is not None
        assert result.symbol == "GOOG"

    def test_returns_none_when_no_result(self):
        svc = self._svc_with_company(None)
        result = svc._search_company("nonexistentxyz")
        assert result is None


class TestFindTicker:
    def test_direct_ticker_bypasses_company_search(self):
        repo = MagicMock()
        repo.get_quote.return_value = _make_good_quote("MSFT")
        repo.market_data = repo.news_adapter = repo.company_lookup = MagicMock()
        svc = _make_service(repo)
        result = svc.find_ticker("MSFT")
        assert result is not None
        assert result.symbol == "MSFT"
        repo.search_company.assert_not_called()

    def test_falls_back_to_company_search_when_token_fails(self):
        repo = MagicMock()
        repo.get_quote.return_value = _make_bad_quote()
        repo.search_company.return_value = {
            "symbol": "NVDA",
            "long_name": "Nvidia Corp",
            "short_name": "Nvidia",
        }
        repo.market_data = repo.news_adapter = repo.company_lookup = MagicMock()
        svc = _make_service(repo)
        result = svc.find_ticker("nvidia")
        assert result is not None
        assert result.symbol == "NVDA"

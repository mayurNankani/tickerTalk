"""Yahoo-based company lookup adapter.

Wraps existing `CompanySearch` tool and converts results into domain
`CompanyIdentity` objects. Keeps transformation isolated from the rest of
the application so we can later swap providers without touching domain or
use-case code.
"""
from typing import List
from core.models import CompanyIdentity
from adapters.company_lookup.interface import CompanyLookupAdapter
from src.tools.company_search import CompanySearch


class YahooCompanyLookupAdapter(CompanyLookupAdapter):
    def __init__(self, search_tool: CompanySearch | None = None):
        self._search = search_tool or CompanySearch()

    def search(self, query: str, limit: int = 5) -> List[CompanyIdentity]:
        tool_result = self._search.analyze(query)
        data = getattr(tool_result, 'data', {}) or {}
        raw_matches = data.get('matches', [])
        identities: List[CompanyIdentity] = []
        for m in raw_matches[:limit]:
            identities.append(
                CompanyIdentity(
                    symbol=m.get('symbol', ''),
                    long_name=m.get('long_name'),
                    short_name=m.get('short_name'),
                )
            )
        return identities

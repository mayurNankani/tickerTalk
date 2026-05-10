"""Protocol for resolving company identity from user queries."""
from typing import Protocol, List
from core.models import CompanyIdentity

class CompanyLookupAdapter(Protocol):
    def search(self, query: str, limit: int = 5) -> List[CompanyIdentity]: ...

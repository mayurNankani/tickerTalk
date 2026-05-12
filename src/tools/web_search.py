"""
Web Search Tool
Performs web searches using DuckDuckGo.
"""

import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
import logging
from urllib.parse import urljoin, urlparse, parse_qs, unquote

logger = logging.getLogger(__name__)


def normalize_result_url(raw_url: str) -> str:
    """Convert DuckDuckGo redirect URLs into direct destination links."""
    if not raw_url:
        return ''

    candidate = raw_url.strip()

    # DuckDuckGo often returns relative redirect links like /l/?uddg=<encoded-url>
    if candidate.startswith('/'):
        candidate = urljoin('https://duckduckgo.com', candidate)
    elif candidate.startswith('//'):
        candidate = f'https:{candidate}'

    # Resolve redirect wrappers (including nested wrappers) up to a small depth.
    for _ in range(3):
        parsed = urlparse(candidate)
        query_params = parse_qs(parsed.query)
        uddg_values = query_params.get('uddg') or []
        if not uddg_values:
            break

        resolved = unquote(uddg_values[0]).strip()
        if not resolved:
            break
        if resolved.startswith('//'):
            resolved = f'https:{resolved}'
        elif resolved.startswith('/'):
            resolved = urljoin('https://duckduckgo.com', resolved)
        candidate = resolved

    # If there is no scheme, treat it as https URL.
    parsed_final = urlparse(candidate)
    if not parsed_final.scheme and parsed_final.netloc:
        return f'https://{candidate}'
    if not parsed_final.scheme and parsed_final.path.startswith('www.'):
        return f'https://{candidate}'

    return candidate


def ddg_search(query: str, max_results: int = 3, timeout: int = 10) -> List[Dict[str, str]]:
    """
    Perform a DuckDuckGo web search.
    
    Args:
        query: The search query
        max_results: Maximum number of results to return
        timeout: Request timeout in seconds
        
    Returns:
        List of search results with title, url, and snippet
    """
    if not query:
        logger.warning("Empty search query provided")
        return []
    
    try:
        # Build search URL
        url = f'https://duckduckgo.com/html/?q={requests.utils.quote(query)}'
        
        # Set browser-like headers
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Referer': 'https://duckduckgo.com/',
            'DNT': '1'
        }
        
        # Perform search
        response = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
        response.raise_for_status()
        
        # Parse results
        soup = BeautifulSoup(response.text, 'html.parser')
        results = _extract_search_results(soup, max_results)
        
        logger.info(f"Found {len(results)} results for query: {query}")
        return results
        
    except requests.exceptions.HTTPError as e:
        logger.error(f"Web search failed with HTTP {e.response.status_code}")
        return []
    except requests.exceptions.Timeout:
        logger.error(f"Web search timed out after {timeout}s")
        return []
    except requests.exceptions.RequestException as e:
        logger.error(f"Web search request failed: {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error during web search: {e}")
        return []


def _extract_search_results(soup: BeautifulSoup, max_results: int) -> List[Dict[str, str]]:
    """Extract search results from DuckDuckGo HTML"""
    results = []
    
    for result_elem in soup.select('.result')[:max_results]:
        try:
            # Extract title
            title_elem = result_elem.select_one('.result__title')
            if not title_elem:
                continue
            title = title_elem.get_text(strip=True)
            
            # Extract link
            link_elem = result_elem.select_one('.result__a')
            if not link_elem or 'href' not in link_elem.attrs:
                continue
            url = normalize_result_url(link_elem['href'])
            if not url:
                continue
            
            # Extract snippet
            snippet_elem = result_elem.select_one('.result__snippet')
            snippet = snippet_elem.get_text(strip=True) if snippet_elem else ''
            
            results.append({
                'title': title,
                'url': url,
                'snippet': snippet
            })
            
        except Exception as e:
            logger.debug(f"Error parsing search result: {e}")
            continue
    
    return results


def search_stock_info(ticker: str, topic: str = "", max_results: int = 3) -> List[Dict[str, str]]:
    """
    Search for stock-related information.
    
    Args:
        ticker: Stock ticker symbol
        topic: Optional topic to include in search
        max_results: Maximum number of results
        
    Returns:
        List of search results
    """
    query = f"{ticker} stock {topic}".strip()
    return ddg_search(query, max_results)


# Backward-compatible alias for any existing imports.
_normalize_result_url = normalize_result_url

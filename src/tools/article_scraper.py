"""
Article Scraper
Fetches and extracts main content from web articles.
"""

import requests
from bs4 import BeautifulSoup
from typing import Optional
import logging

logger = logging.getLogger(__name__)


def fetch_article_text(url: str, timeout: int = 10) -> str:
    """
    Fetch and extract the main text content from a news article URL.
    
    Args:
        url: The article URL to fetch
        timeout: Request timeout in seconds
        
    Returns:
        Article text or error message
    """
    if not url:
        return "(No URL provided)"
    
    try:
        headers = _get_browser_headers()
        response = requests.get(
            url,
            headers=headers,
            timeout=timeout,
            allow_redirects=True
        )
        response.raise_for_status()
        
        # Parse HTML
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Try multiple extraction strategies
        text = _try_article_tag(soup)
        if text:
            return text
        
        text = _try_largest_div(soup)
        if text:
            return text
        
        text = _try_paragraph_tags(soup)
        if text:
            return text
        
        # Fallback: return first 500 chars of page
        return soup.get_text(separator=' ', strip=True)[:500]
        
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 403:
            return "(Access forbidden - website blocking automated requests)"
        return f"(HTTP error {e.response.status_code})"
    except requests.exceptions.Timeout:
        return "(Request timed out)"
    except requests.exceptions.RequestException as e:
        logger.warning(f"Request error for {url}: {e}")
        return f"(Network error: {str(e)[:50]})"
    except Exception as e:
        logger.error(f"Unexpected error scraping {url}: {e}")
        return f"(Error: {str(e)[:50]})"


def _get_browser_headers() -> dict:
    """Get realistic browser headers"""
    return {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Referer': 'https://www.google.com/'
    }


def _try_article_tag(soup: BeautifulSoup) -> Optional[str]:
    """Try to extract content from <article> tag"""
    article = soup.find('article')
    if article:
        text = article.get_text(separator=' ', strip=True)
        if len(text) > 200:
            return text
    return None


def _try_largest_div(soup: BeautifulSoup) -> Optional[str]:
    """Find the div with the most text content"""
    divs = soup.find_all('div')
    if not divs:
        return None
    
    # Sort by text length
    sorted_divs = sorted(divs, key=lambda d: len(d.get_text()), reverse=True)
    
    for div in sorted_divs[:5]:  # Check top 5 largest divs
        text = div.get_text(separator=' ', strip=True)
        if len(text) > 200:
            return text
    return None


def _try_paragraph_tags(soup: BeautifulSoup) -> Optional[str]:
    """Concatenate all paragraph tags"""
    paragraphs = soup.find_all('p')
    if not paragraphs:
        return None
    
    text = ' '.join(p.get_text(separator=' ', strip=True) for p in paragraphs)
    if len(text) > 200:
        return text
    return None

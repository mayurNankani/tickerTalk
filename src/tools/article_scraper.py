import requests
from bs4 import BeautifulSoup

def fetch_article_text(url: str) -> str:
    """
    Fetch and extract the main text content from a news article URL.
    Returns a short string if extraction fails.
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        resp = requests.get(url, headers=headers, timeout=10, allow_redirects=True)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')
        # Try to extract main content heuristically
        # 1. Look for <article> tag
        article = soup.find('article')
        if article:
            text = article.get_text(separator=' ', strip=True)
            if len(text) > 200:
                return text
        # 2. Fallback: look for largest <div> by text length
        divs = soup.find_all('div')
        divs = sorted(divs, key=lambda d: len(d.get_text()), reverse=True)
        for div in divs:
            text = div.get_text(separator=' ', strip=True)
            if len(text) > 200:
                return text
        # 3. Fallback: all <p> tags concatenated
        ps = soup.find_all('p')
        text = ' '.join(p.get_text(separator=' ', strip=True) for p in ps)
        if len(text) > 200:
            return text
        # If all else fails, return first 500 chars of page
        return soup.get_text(separator=' ', strip=True)[:500]
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 403:
            return "(Access forbidden - website is blocking automated requests.)"
        return f"(HTTP error {e.response.status_code})"
    except requests.exceptions.Timeout:
        return "(Request timed out.)"
    except Exception as e:
        return f"(Could not fetch article content: {str(e)[:50]})"

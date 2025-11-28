import requests

def ddg_search(query, max_results=3):
    """
    Perform a DuckDuckGo Instant Answer API search (free, no API key required).
    Returns a list of dicts: [{'title': ..., 'url': ..., 'snippet': ...}, ...]
    """
    try:
        url = f'https://duckduckgo.com/html/?q={requests.utils.quote(query)}'
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.text, 'html.parser')
        results = []
        for res in soup.select('.result')[:max_results]:
            title = res.select_one('.result__title')
            link = res.select_one('.result__a')
            snippet = res.select_one('.result__snippet')
            if title and link:
                results.append({
                    'title': title.get_text(strip=True),
                    'url': link['href'],
                    'snippet': snippet.get_text(strip=True) if snippet else ''
                })
        return results
    except Exception:
        return []

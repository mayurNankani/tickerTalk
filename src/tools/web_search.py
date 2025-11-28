import requests

def ddg_search(query, max_results=3):
    """
    Perform a DuckDuckGo Instant Answer API search (free, no API key required).
    Returns a list of dicts: [{'title': ..., 'url': ..., 'snippet': ...}, ...]
    """
    try:
        url = f'https://duckduckgo.com/html/?q={requests.utils.quote(query)}'
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Referer': 'https://duckduckgo.com/'
        }
        resp = requests.get(url, headers=headers, timeout=10, allow_redirects=True)
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
    except requests.exceptions.HTTPError as e:
        print(f"Web search failed with HTTP {e.response.status_code}")
        return []
    except Exception as e:
        print(f"Web search failed: {str(e)[:100]}")
        return []

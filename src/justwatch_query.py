import urllib.parse
from bs4 import BeautifulSoup
import re

def get_localized_search_url(page, country, film_title):
    base_url = f"https://www.justwatch.com/{country}"
    page.goto(base_url, wait_until="domcontentloaded")
    soup = BeautifulSoup(page.content(), 'html.parser')
    
    search_path = None
    # JustWatch JP often uses /jp/作品を検索 or simply /jp/search
    for link in soup.find_all("a", href=True):
        href = link['href']
        if href.startswith(f"/{country}/") and any(w in href.lower() for w in ["search", "buscar", "recherche", "suche", "cerca", "作品を検索"]):
            search_path = href
            break
    
    if not search_path:
        search_path = f"/{country}/search"
        
    query = urllib.parse.quote(film_title)
    return f"https://www.justwatch.com{search_path}?q={query}"

def get_film_offers(page, title, year, country):
    print(f"--- Processing: {title} ({year}) in {country.upper()} ---")
    
    try:
        target_search_url = get_localized_search_url(page, country, f"{title} {year}")
        page.goto(target_search_url, wait_until="networkidle")

        try:
            page.wait_for_selector("picture img", timeout=10000)
        except:
            return []

        soup = BeautifulSoup(page.content(), 'html.parser')
        pattern = re.compile(rf"^/{country}/[^/]+/[^/]+$")
        movie_links = [a['href'] for a in soup.find_all("a", href=True) if pattern.match(a['href']) and not any(x in a['href'] for x in ["/search", "/buscar", "/list"])]

        if not movie_links:
            return []

        movie_url = f"https://www.justwatch.com{movie_links[0]}"
        print(f"   ✅ Target: {movie_url}")

        page.goto(movie_url, wait_until="domcontentloaded")
        page.wait_for_selector(".buybox-row", timeout=15000)
        
        final_soup = BeautifulSoup(page.content(), 'html.parser')
        providers = []
        
        # GLOBAL STREAM KEYWORDS
        # Added: 動画配信 (JP), 定額制 (JP), Subscription (General)
        stream_keywords = [
            "stream", "suscripción", "flatrate", "diffuser", "online", 
            "reproducción", "動画配信", "定額制", "subscription"
        ]

        rows = final_soup.select(".buybox-row")
        for row in rows:
            label = row.select_one(".buybox-row__label")
            if label:
                label_text = label.get_text().lower()
                # Check if the label matches any of our global keywords
                if any(kw in label_text for kw in stream_keywords):
                    for img in row.select("a.offer img"):
                        name = img.get('alt')
                        if name and name.lower() != "justwatch":
                            providers.append(name)
        
        return list(set(providers))

    except Exception as e:
        print(f"   ⚠️ Error: {e}")
        return []
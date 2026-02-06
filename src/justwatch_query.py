import urllib.parse
from bs4 import BeautifulSoup
import re

# FIXED MAPPING FOR YOUR COUNTRIES
SEARCH_SLUGS = {
    "us": "search",
    "uk": "search",
    "ca": "search",
    "au": "search",
    "dk": "search",
    "za": "search",
    "es": "buscar",
    "ar": "buscar",
    "jp": "検索"
}

def get_film_offers(page, title, year, country):
    # Determine the slug from our mapping
    slug = SEARCH_SLUGS.get(country.lower(), "search")
    query = urllib.parse.quote(f"{title} {year}")
    search_url = f"https://www.justwatch.com/{country}/{slug}?q={query}"
    
    print(f"--- Processing: {title} ({year}) in {country.upper()} ---")
    
    try:
        # Use 'domcontentloaded' to avoid waiting for heavy ad trackers
        page.goto(search_url, wait_until="domcontentloaded", timeout=20000)
        
        # Step 1: Identify the movie link
        try:
            page.wait_for_selector("a[href*='/']", timeout=10000)
        except:
            return []

        soup = BeautifulSoup(page.content(), 'html.parser')
        
        # Localized movie path segments
        movie_identifiers = ["movie", "pelicula", "film", "filme", "映画"]
        
        movie_links = []
        for a in soup.find_all("a", href=True):
            href = a['href']
            # Regex checks for the structure: /country/something/title
            if re.match(rf"^/{country}/[^/]+/[^/]+$", href):
                # Ensure it's a movie and not a TV show or search utility
                if any(x in href.lower() for x in movie_identifiers) and "tv" not in href.lower():
                    if not any(u in href.lower() for u in ["search", "buscar", "list","検索"]):
                        movie_links.append(href)

        if not movie_links:
            print(f"   ❌ No movie link found for {title}")
            return []

        movie_url = f"https://www.justwatch.com{movie_links[0]}"
        print(f"   ✅ Target: {movie_url}")

        # Step 2: Extract Streaming Providers
        page.goto(movie_url, wait_until="domcontentloaded", timeout=20000)
        
        try:
            # Short wait for the offer box
            page.wait_for_selector(".buybox-row", timeout=5000)
        except:
            return [] # No streaming info available

        final_soup = BeautifulSoup(page.content(), 'html.parser')
        providers = []
        
        # Keywords to catch 'Streaming' row globally
        stream_keywords = ["stream", "suscripción", "suscripcion", "flatrate", "diffuser", "動画配信", "定額制", "online"]

        for row in final_soup.select(".buybox-row"):
            label = row.select_one(".buybox-row__label")
            if label and any(kw in label.get_text().lower() for kw in stream_keywords):
                for img in row.select("a.offer img"):
                    name = img.get('alt')
                    if name and name.lower() != "justwatch":
                        providers.append(name)
        
        return list(set(providers))

    except Exception as e:
        print(f"   ⚠️ Error: {str(e)[:50]}")
        return []
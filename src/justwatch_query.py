import urllib.parse
from bs4 import BeautifulSoup
import re
import time

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

def validate_year(target_year, found_text):
    """
    Checks if the text contains the target year (with +/- 1 year tolerance).
    """
    if not found_text: return False
    
    # Regex for 4 digits (e.g., "(1965)" or " 1965 ")
    match = re.search(r'(?:^|\s|\()(\d{4})(?:\)|\s|$)', found_text)
    if match:
        found_year = int(match.group(1))
        # Allow +/- 1 year difference (e.g. 1965 matches 1964, 1965, 1966)
        if abs(target_year - found_year) <= 1:
            return True
    return False

def perform_search(page, country, query, target_year):
    """
    Helper to run a single search query and return the first valid match URL.
    """
    slug = SEARCH_SLUGS.get(country.lower(), "search")
    encoded_query = urllib.parse.quote(query)
    search_url = f"https://www.justwatch.com/{country}/{slug}?q={encoded_query}"

    print(f"   🔎 Searching for: '{query}'...")
    
    try:
        page.goto(search_url, wait_until="domcontentloaded", timeout=20000)
        
        # Wait for results row OR the 'no results' indicator
        try:
            page.wait_for_selector(".title-list-row, .horizontal-title-list", timeout=5000)
        except:
            return None # Search likely timed out or returned nothing

        soup = BeautifulSoup(page.content(), 'html.parser')
        
        movie_identifiers = ["movie", "pelicula", "film", "filme", "映画"]
        exclude_terms = ["search", "buscar", "list", "検索", "tv-show", "serie", "season"]
        
        # STOP scanning if we hit these section headers (to avoid random recommendations)
        stop_keywords = ["próximas", "coming soon", "recomendados", "recommended", "related", "watch next"]

        for a in soup.find_all("a", href=True):
            href = a['href']
            
            # Check if we've scrolled too far into 'Recommendations'
            # We check the parent/preceding header if possible, or just the link text itself 
            # (JustWatch often puts these in distinct sections, but simple text checking helps)
            
            if re.match(rf"^/{country}/[^/]+/[^/]+$", href):
                if any(mid in href.lower() for mid in movie_identifiers) and not any(ex in href.lower() for ex in exclude_terms):
                    
                    # Get Text
                    link_text = a.get_text(" ", strip=True)
                    if not link_text: # Fallback to Image Alt
                        img = a.find("img")
                        if img and img.get("alt"):
                            link_text = img.get("alt")

                    # Validations
                    is_match = validate_year(target_year, link_text)
                    
                    # Debug print
                    # print(f"      Checking: '{link_text}' -> {'✅' if is_match else '❌'}")

                    if is_match:
                        return f"https://www.justwatch.com{href}"
                        
    except Exception as e:
        print(f"      ⚠️ Search Error: {e}")
    
    return None

def get_film_offers(page, title, year, country):
    try:
        target_year = int(year)
    except:
        return []

    print(f"--- Processing: {title} ({target_year}) in {country.upper()} ---")

    # --- STRATEGY 1: SPECIFIC SEARCH (Title + Year) ---
    # Good for common titles like "Red", "Halloween"
    target_url = perform_search(page, country, f"{title} {target_year}", target_year)

    # --- STRATEGY 2: BROAD SEARCH (Title Only) ---
    # If #1 failed, try searching JUST the title.
    # This fixes "Red Beard 1965" failing but "Red Beard" finding "Barbarroja (1965)"
    if not target_url:
        print("   ⚠️ Specific search failed. Retrying with Broad Search (Title only)...")
        target_url = perform_search(page, country, title, target_year)

    if not target_url:
        print(f"   ❌ Failed to find '{title}' ({target_year}) after retries.")
        return []

    print(f"   ✅ Target Found: {target_url}")

    # --- STEP 3: GET OFFERS ---
    try:
        page.goto(target_url, wait_until="domcontentloaded", timeout=20000)
        try:
            page.wait_for_selector(".buybox-row", timeout=5000)
        except:
            print("   ℹ️ No streaming offers found.")
            return []

        final_soup = BeautifulSoup(page.content(), 'html.parser')
        providers = []
        stream_keywords = ["stream", "suscripción", "suscripcion", "flatrate", "diffuser", "online", "tarifa plana"]

        for row in final_soup.select(".buybox-row"):
            label = row.select_one(".buybox-row__label")
            if label:
                label_text = label.get_text().lower()
                if any(kw in label_text for kw in stream_keywords):
                    for img in row.select("a.offer img"):
                        name = img.get('alt')
                        if name and name.lower() != "justwatch":
                            providers.append(name)
        
        return list(set(providers))

    except Exception as e:
        print(f"   ⚠️ Extraction Error: {e}")
        return []
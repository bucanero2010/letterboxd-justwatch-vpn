import urllib.parse
from bs4 import BeautifulSoup
import re
import time

# --- CONFIG ---
SEARCH_SLUGS = {
    "us": "search", "uk": "search", "ca": "search", "au": "search", 
    "dk": "search", "za": "search", "es": "buscar", "ar": "buscar", "jp": "検索"
}

def normalize(text):
    """Lowercase, strip accents, remove punctuation for fuzzy comparison."""
    import unicodedata
    text = unicodedata.normalize('NFD', text.lower())
    text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
    text = re.sub(r'[^\w\s]', '', text)
    return text.strip()

def validate_match(target_title, target_year, found_text):
    if not found_text: return False
    # Check year (allow ±1 year tolerance)
    match = re.search(r'(?:^|\s|\()(\d{4})(?:\)|\s|$)', found_text)
    if not match: return False
    if abs(target_year - int(match.group(1))) > 1: return False
    # Check title word overlap
    target_words = set(normalize(target_title).split())
    found_norm = normalize(found_text)
    found_words = set(found_norm.split())
    # Remove very short/common words
    stopwords = {'the', 'a', 'an', 'of', 'in', 'on', 'at', 'to', 'and', 'or',
                 'el', 'la', 'los', 'las', 'de', 'del', 'en', 'un', 'una', 'y',
                 'le', 'les', 'des', 'du', 'et', 'der', 'die', 'das', 'und'}
    significant = {w for w in target_words if len(w) > 2 and w not in stopwords}
    if not significant:
        significant = target_words
    # For short titles (1-2 significant words), require all to match
    # For longer titles, require at least half
    matched = sum(1 for w in significant if w in found_words or w in found_norm)
    if len(significant) <= 2:
        return matched >= len(significant)
    return matched >= max(2, len(significant) // 2)

def perform_search(page, country, query, target_year, original_title=None):
    """Search JustWatch. original_title is used for match validation (defaults to query)."""
    match_title = original_title or query
    slug = SEARCH_SLUGS.get(country.lower(), "search")
    encoded_query = urllib.parse.quote(query)
    search_url = f"https://www.justwatch.com/{country}/{slug}?q={encoded_query}"

    print(f"   🔎 Searching for: '{query}'...")
    try:
        # 1920x1080 ensures the Grid/List toolbar is actually rendered in the DOM
        page.set_viewport_size({"width": 1920, "height": 1080})
        page.goto(search_url, wait_until="domcontentloaded", timeout=20000)
        
        try:
            page.wait_for_selector(".title-list-row, .horizontal-title-list", timeout=5000)
        except:
            return None 

        soup = BeautifulSoup(page.content(), 'html.parser')

        # NEW: Search results now use title-list-row with column-header links
        # href can be absolute (https://www.justwatch.com/us/movie/...) or relative (/us/movie/...)
        for header_link in soup.select("a.title-list-row__column-header"):
            href = header_link.get("href", "")
            # Normalize: strip domain prefix if present
            path = href.replace("https://www.justwatch.com", "")
            if not re.match(rf"^/{country}/[^/]+/[^/]+$", path):
                continue
            movie_keywords = ["movie", "pelicula", "film", "filme", "映画"]
            if not any(kw in path for kw in movie_keywords):
                continue
            link_text = header_link.get_text(" ", strip=True)
            if validate_match(match_title, target_year, link_text):
                return f"https://www.justwatch.com{path}"

        # FALLBACK: Legacy approach for older layouts
        for a in soup.find_all("a", href=True):
            href = a['href']
            path = href.replace("https://www.justwatch.com", "")
            if re.match(rf"^/{country}/[^/]+/[^/]+$", path):
                if any(x in path for x in ["movie", "pelicula", "film", "filme", "映画"]):
                    link_text = a.get_text(" ", strip=True) or (a.find("img").get("alt") if a.find("img") else "")
                    if validate_match(match_title, target_year, link_text):
                        return f"https://www.justwatch.com{path}"
    except:
        pass
    return None

def ensure_grid_view(page):
    """
    Switches to Grid View using the exact 'div' text locator found via Codegen.
    """
    # JustWatch localized terms for "Grid"
    grid_terms = [r"^Grid$", r"^Grilla$", r"^Mosaico$", r"^グリッド$"]
    
    for term in grid_terms:
        try:
            locator = page.locator("div").filter(has_text=re.compile(term))
            if locator.count() > 0:
                if locator.first.is_visible():
                    locator.first.click(timeout=1000)
                    time.sleep(0.5) # Wait for DOM update as requested
                    return True
        except:
            continue
    return False

def get_film_offers(page, title, year, country, local_title=None):
    try:
        target_year = int(year)
    except:
        return []

    # Try localized title first if available and different from English
    target_url = None
    if local_title and local_title.lower() != title.lower():
        target_url = perform_search(page, country, f"{local_title} {target_year}", target_year, original_title=local_title)
        if not target_url:
            target_url = perform_search(page, country, local_title, target_year, original_title=local_title)

    # Fall back to English title
    if not target_url:
        target_url = perform_search(page, country, f"{title} {target_year}", target_year, original_title=title)
    if not target_url:
        target_url = perform_search(page, country, title, target_year, original_title=title)

    if not target_url:
        return []

    print(f"   ✅ Target Found: {target_url}")

    try:
        page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
        
        if "Verify" in page.title() or "Cloudflare" in page.title():
            return []

        # 1. Scroll down to trigger lazy loading, then wait
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(1)

        # 2. Switch to Grid
        ensure_grid_view(page)

        # 3. Wait for Content with retry
        rows = []
        for attempt in range(3):
            try:
                page.wait_for_selector(".buybox-row, .price-comparison__grid__row", timeout=5000)
            except:
                pass
            final_soup = BeautifulSoup(page.content(), 'html.parser')
            rows = final_soup.select(".buybox-row, .price-comparison__grid__row")
            if rows:
                break
            # Scroll again and wait before retry
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(1.5)

        if not rows:
            return []

        providers = []
        
        for row in rows:
            is_streaming = False
            
            row_classes = row.get("class", [])
            class_str = " ".join(row_classes).lower()
            
            if "stream" in class_str or "flatrate" in class_str:
                if "rent" not in class_str and "buy" not in class_str:
                    is_streaming = True

            if not is_streaming:
                label = row.select_one(".buybox-row__label, .price-comparison__grid__row__label")
                if label:
                    txt = label.get_text().strip().lower()
                    stream_keywords = ["stream", "suscripción", "flatrate", "online", "動画配信", "定額制", "見放題"]
                    if any(k in txt for k in stream_keywords):
                        if not any(bad in txt for bad in ["rent", "buy", "purchase", "alquilar", "comprar", "レンタル", "購入"]):
                            is_streaming = True

            if is_streaming:
                # NEW: Extract from a.offer > img.provider-icon (current layout)
                for offer_link in row.select("a.offer"):
                    img = offer_link.select_one("img.provider-icon, img")
                    if img:
                        name = img.get('alt') or img.get('title')
                        if name and "justwatch" not in name.lower():
                            providers.append(name)
                
                # FALLBACK: Direct img scan for older layouts
                if not providers:
                    for img in row.select("img"):
                        name = img.get('alt') or img.get('title')
                        if name and "justwatch" not in name.lower():
                            providers.append(name)
        
        providers = list(set(providers))
        
        if providers:
            print(f"   🎉 Found: {', '.join(providers)}")

        return providers

    except Exception:
        return []
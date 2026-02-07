import urllib.parse
from bs4 import BeautifulSoup
import re
import time

# --- CONFIG ---
SEARCH_SLUGS = {
    "us": "search", "uk": "search", "ca": "search", "au": "search", 
    "dk": "search", "za": "search", "es": "buscar", "ar": "buscar", "jp": "検索"
}

def validate_match(target_title, target_year, found_text):
    if not found_text: return False
    match = re.search(r'(?:^|\s|\()(\d{4})(?:\)|\s|$)', found_text)
    if not match: return False
    if abs(target_year - int(match.group(1))) > 1: return False
    return True 

def perform_search(page, country, query, target_year):
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
        for a in soup.find_all("a", href=True):
            href = a['href']
            if re.match(rf"^/{country}/[^/]+/[^/]+$", href):
                if any(x in href for x in ["movie", "pelicula", "film", "filme", "映画"]):
                    link_text = a.get_text(" ", strip=True) or (a.find("img").get("alt") if a.find("img") else "")
                    if validate_match(query.split()[0], target_year, link_text):
                        return f"https://www.justwatch.com{href}"
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

def get_film_offers(page, title, year, country):
    try:
        target_year = int(year)
    except:
        return []

    target_url = perform_search(page, country, f"{title} {target_year}", target_year)
    if not target_url:
        target_url = perform_search(page, country, title, target_year)

    if not target_url:
        return []

    print(f"   ✅ Target Found: {target_url}")

    try:
        page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
        
        if "Verify" in page.title() or "Cloudflare" in page.title():
            return []

        # 1. Scroll Down (Vital for lazy loading offers)
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(0.1)

        # 2. Switch to Grid
        ensure_grid_view(page)

        # 3. Wait for Content
        try:
            page.wait_for_selector(".buybox-row, .price-comparison__grid__row", timeout=5000)
        except:
            return []

        final_soup = BeautifulSoup(page.content(), 'html.parser')
        providers = []
        
        # 4. Extract (Universal Logic)
        rows = final_soup.select(".buybox-row, .price-comparison__grid__row")
        
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
                for img in row.select("img"):
                    name = img.get('alt') or img.get('title')
                    if name and "justwatch" not in name.lower():
                        providers.append(name)
                
                if not providers:
                    for link in row.select("a"):
                        img = link.find("img")
                        if img:
                             name = img.get('alt') or img.get('title')
                             if name and "justwatch" not in name.lower():
                                providers.append(name)
        
        providers = list(set(providers))
        
        if providers:
            print(f"   🎉 Found: {', '.join(providers)}")

        return providers

    except Exception:
        return []
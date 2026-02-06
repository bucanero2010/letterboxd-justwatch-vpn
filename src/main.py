import json
import pandas as pd
import time
import random
from pathlib import Path
from playwright.sync_api import sync_playwright

# --- LOCAL MODULES ---
# Note: Ensure your scrape_films function in letterbox_scraper.py 
# is updated to accept the 'page' object.
from letterbox_scraper import scrape_films_browser as scrape_films 
from matcher import get_unwatched
from justwatch_query import get_film_offers
from poster_service import get_poster_url

# --- SMART PATHING ---
SCRIPT_DIR = Path(__file__).resolve().parent
BASE_DIR = SCRIPT_DIR.parent 
DATA_DIR = BASE_DIR / "data"
OUTPUT_FILE = DATA_DIR / "unwatched_by_country.csv"

DATA_DIR.mkdir(parents=True, exist_ok=True)

def load_config():
    paths = [SCRIPT_DIR / "config.json", BASE_DIR / "config.json"]
    for p in paths:
        if p.exists():
            with open(p, "r") as f:
                return json.load(f)
    raise FileNotFoundError("❌ config.json not found")

def main():
    config = load_config()
    USERNAME = config["letterboxd_user"]
    TMDB_TOKEN = config["tmdb_key"]
    COUNTRIES = config.get("country_scan", ["US"])

    rows = []
    poster_cache = {} 

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={'width': 1920, 'height': 1080}
        )

        # --- THE STEALTH SAUCE ---
        # This script deletes the 'webdriver' property so sites can't see it
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)
        
        page = context.new_page()

        # --- 1. FETCH LETTERBOXD DATA (Now using Playwright Page) ---
        print(f"--- Fetching Letterboxd data for {USERNAME} ---")
        
        # We pass 'page' so the scraper can use the active browser session
        watched = scrape_films(page, f"https://letterboxd.com/{USERNAME}/films/")
        watchlist = scrape_films(page, f"https://letterboxd.com/{USERNAME}/watchlist/")
        
        unwatched = get_unwatched(watchlist, watched)
        print(f"✅ Found {len(unwatched)} unwatched films.")

        if not unwatched:
            print("No new films to scan. Exiting.")
            browser.close()
            return

        # --- 2. JUSTWATCH SCAN ---
        for country in COUNTRIES:
            print(f"\n🌍 SCANNING: {country.upper()}")
            
            for film in unwatched:
                # Get/Cache Poster URL (API call, no browser needed here)
                movie_id = f"{film['title']}_{film['year']}"
                if movie_id not in poster_cache:
                    print(f"🎬 Getting poster: {film['title']}")
                    poster_cache[movie_id] = get_poster_url(film["title"], film["year"], TMDB_TOKEN)
                
                # Scrape JustWatch using the SAME page object
                print(f"🔍 Checking availability for: {film['title']}")
                offers = get_film_offers(page, film["title"], film["year"], country.lower())
                
                if offers:
                    for o in offers:
                        rows.append({
                            "title": film["title"],
                            "year": film["year"],
                            "country": country.upper(),
                            "provider": o,
                            "poster_url": poster_cache[movie_id]
                        })
                
                # Politeness delay
                time.sleep(random.uniform(1, 2))

        browser.close()

    # --- 3. SAVE RESULTS ---
    if rows:
        df = pd.DataFrame(rows)
        df.to_csv(OUTPUT_FILE, index=False)
        print(f"\n✅ Results saved to: {OUTPUT_FILE}")
    else:
        print("\nℹ️ No streaming offers found for the selected countries.")

if __name__ == "__main__":
    main()
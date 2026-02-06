import json
import pandas as pd
import time
import random
from pathlib import Path
from playwright.sync_api import sync_playwright

# --- LOCAL MODULES ---
from letterbox_scraper import scrape_films
from justwatch_query import get_film_offers
from poster_service import get_poster_url  # <--- New Import

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

    print(f"--- Fetching Letterboxd data for {USERNAME} ---")
    unwatched = scrape_films(f"https://letterboxd.com/{USERNAME}/watchlist/")
    
    rows = []
    poster_cache = {} # Dictionary to avoid redundant API calls

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent="Mozilla/5.0 ...")
        page = context.new_page()

        for country in COUNTRIES:
            print(f"\n🌍 SCANNING: {country.upper()}")
            
            # Remove [:4] when you are ready to run the full list
            for film in unwatched:
                # 1. Get/Cache Poster URL
                movie_id = f"{film['title']}_{film['year']}"
                if movie_id not in poster_cache:
                    print(f"🎬 Getting poster: {film['title']}")
                    poster_cache[movie_id] = get_poster_url(film["title"], film["year"], TMDB_TOKEN)
                
                # 2. Scrape JustWatch
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
                
                time.sleep(random.uniform(1, 2))

        browser.close()

    if rows:
        df = pd.DataFrame(rows)
        df.to_csv(OUTPUT_FILE, index=False)
        print(f"\n✅ Results saved to: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
import json
import pandas as pd
import time
import random
import re
from datetime import datetime
from pathlib import Path
from playwright.sync_api import sync_playwright

# --- LOCAL MODULES ---
from letterbox_scraper import scrape_films
from justwatch_query import get_film_offers
from poster_service import get_movie_metadata

# --- PATHS ---
SCRIPT_DIR = Path(__file__).resolve().parent
BASE_DIR = SCRIPT_DIR.parent 
DATA_DIR = BASE_DIR / "data"
OUTPUT_FILE = DATA_DIR / "unwatched_by_country.csv"
WATCHLIST_HISTORY = DATA_DIR / "seen_watchlist.json"

DATA_DIR.mkdir(parents=True, exist_ok=True)

def load_config():
    paths = [SCRIPT_DIR / "config.json", BASE_DIR / "config.json"]
    for p in paths:
        if p.exists():
            with open(p, "r") as f:
                return json.load(f)
    raise FileNotFoundError("❌ config.json not found")

def get_history():
    if WATCHLIST_HISTORY.exists():
        with open(WATCHLIST_HISTORY, "r") as f:
            return set(json.load(f))
    return set()

def save_history(history_set):
    with open(WATCHLIST_HISTORY, "w") as f:
        json.dump(list(history_set), f)

# --- THE CLEANING FUNCTION ---
def clean_provider_name(name):
    if not name or pd.isna(name):
        return name
    
    # 1. Remove specific add-on suffixes (Amazon Channel, Apple Channel, etc)
    name = re.sub(r'\s*(?:on\s+)?(?:Amazon|Apple TV|U-Next|BFI|Curzon|Studiocanal)\s+Channel.*', '', name, flags=re.IGNORECASE)
    
    # 2. Remove tier and ad descriptors
    name = re.sub(r'\s*(?:with Ads|Standard with Ads|Basic with Ads|Premium|Essential|Total|Ficción Total|Player|Extra|Basic|on U-Next).*', '', name, flags=re.IGNORECASE)

    # 3. Specific manual cleanup
    name = name.replace("Paramount Plus", "Paramount+")
    name = name.replace("AMC Plus", "AMC+")
    
    return name.strip()

def main():
    config = load_config()
    USERNAME = config["letterboxd_user"]
    TMDB_TOKEN = config["tmdb_key"]
    COUNTRIES = config.get("country_scan", ["US"])

    # 1. Fetch current watchlist
    print(f"--- Fetching Letterboxd data for {USERNAME} ---")
    current_watchlist = scrape_films(f"https://letterboxd.com/{USERNAME}/watchlist/")
    
    # 2. Determine Scan Mode
    today = datetime.today()
    is_sunday = today.weekday() == 6
    is_first_of_month = today.day == 1
    is_full_scan = is_sunday or is_first_of_month

    history = get_history()
    current_ids = {f"{f['title']}_{f['year']}" for f in current_watchlist}
    
    if is_full_scan:
        print(f"📅 {today.strftime('%Y-%m-%d')}: FULL SCAN TRIGGERED (Sunday/1st of Month)")
        films_to_scan = current_watchlist
    else:
        print(f"📅 {today.strftime('%Y-%m-%d')}: DAILY SCAN (New movies only)")
        films_to_scan = [f for f in current_watchlist if f"{f['title']}_{f['year']}" not in history]

    if not films_to_scan:
        print("☕ No new movies to check. Exiting.")
        save_history(current_ids) # Update history to reflect current watchlist
        return

    print(f"🚀 Processing {len(films_to_scan)} movies...")

    rows = []
    movie_cache = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent="Mozilla/5.0 ...")
        page = context.new_page()

        for country in COUNTRIES:
            print(f"\n🌍 SCANNING: {country.upper()}")
            
            for film in films_to_scan:
                movie_id = f"{film['title']}_{film['year']}"

                # 1. Metadata Cache
                if movie_id not in movie_cache:
                    poster, runtime = get_movie_metadata(film["title"], film["year"], TMDB_TOKEN)
                    movie_cache[movie_id] = {"poster_url": poster, "runtime": runtime}

                # 2. Scrape JustWatch
                offers = get_film_offers(page, film["title"], film["year"], country.lower())
                
                if offers:
                    # Use a set to immediately de-duplicate the cleaned names
                    unique_cleaned_providers = set()
                    for o in offers:
                        cleaned = clean_provider_name(o)
                        unique_cleaned_providers.add(cleaned)

                    for provider in unique_cleaned_providers:
                        rows.append({
                            "title": film["title"],
                            "year": film["year"],
                            "country": country.upper(),
                            "provider": provider, # Storing the clean version
                            "poster_url": movie_cache[movie_id]["poster_url"],
                            "runtime": movie_cache[movie_id]["runtime"],
                            "last_updated": today.strftime("%Y-%m-%d")
                        })
                
                time.sleep(random.uniform(0.1, 0.3))

        browser.close()

    # 3. Handle Results
    if rows:
        new_df = pd.DataFrame(rows)
        if is_full_scan or not OUTPUT_FILE.exists():
            # Overwrite on full scan
            new_df.to_csv(OUTPUT_FILE, index=False)
        else:
            # Append on daily scan, but remove duplicates for the same movie/country/provider
            existing_df = pd.read_csv(OUTPUT_FILE)
            combined_df = pd.concat([existing_df, new_df]).drop_duplicates(
                subset=["title", "year", "country", "provider"], keep="last"
            )
            combined_df.to_csv(OUTPUT_FILE, index=False)
        
        print(f"\n✅ Results updated in: {OUTPUT_FILE}")

    # 4. Update history so we don't scan these again tomorrow
    save_history(current_ids)

if __name__ == "__main__":
    main()
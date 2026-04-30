import json
import os
import pandas as pd
import time
import random
import re
from datetime import datetime
from pathlib import Path
from playwright.sync_api import sync_playwright

# --- LOCAL MODULES ---
from letterbox_scraper import scrape_films, discover_lists
from justwatch_query import get_film_offers_api
from poster_service import get_movie_metadata, get_localized_title
from alert_service import find_new_availability, send_alert_email

# --- PATHS ---
SCRIPT_DIR = Path(__file__).resolve().parent
BASE_DIR = SCRIPT_DIR.parent 
DATA_DIR = BASE_DIR / "data"
OUTPUT_FILE = DATA_DIR / "unwatched_by_country.csv"
DATA_DIR.mkdir(parents=True, exist_ok=True)

def load_config():
    paths = [SCRIPT_DIR / "config.json", BASE_DIR / "config.json"]
    config = None
    for p in paths:
        if p.exists():
            with open(p, "r") as f:
                config = json.load(f)
            break
    if config is None:
        raise FileNotFoundError("❌ config.json not found")

    # Allow environment variable to override sensitive config (for CI/production)
    env_tmdb = os.environ.get("TMDB_TOKEN")
    if env_tmdb:
        config["tmdb_key"] = env_tmdb

    return config

def get_history_path(source_key: str) -> Path:
    """Return the history file path for a given source key."""
    return DATA_DIR / f"seen_{source_key}.json"

def load_history(source_key: str) -> set:
    """Load history for a specific source. Returns empty set if missing or corrupt."""
    path = get_history_path(source_key)
    if path.exists():
        try:
            with open(path, "r") as f:
                return set(json.load(f))
        except (json.JSONDecodeError, ValueError):
            return set()
    return set()

def save_history(source_key: str, history_set: set):
    """Save history for a specific source."""
    path = get_history_path(source_key)
    with open(path, "w") as f:
        json.dump(list(history_set), f)

def clean_provider_name(name):
    if not name or pd.isna(name):
        return name
    
    # 1. Remove specific add-on suffixes
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

    # --- 1. Discover sources (Task 4.1) ---
    print(f"--- Fetching Letterboxd data for {USERNAME} ---")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        page = context.new_page()

        sources = [{'name': 'Watchlist', 'url': f'https://letterboxd.com/{USERNAME}/watchlist/', 'key': 'watchlist'}]
        try:
            discovered = discover_lists(USERNAME, pw_page=page)
        except Exception as e:
            print(f"⚠️ Failed to discover lists: {e}")
            discovered = []

        for lst in discovered:
            sources.append({
                'name': lst['name'],
                'url': f"https://letterboxd.com{lst['url']}",
                'key': f"list_{lst['slug']}",
            })
        print(f"📋 Found {len(sources)} sources: {', '.join(s['name'] for s in sources)}")

        # --- 2. Determine scan mode ---
        today = datetime.today()
        is_full_scan = today.weekday() == 6 or today.day == 1

        if is_full_scan:
            print(f"📅 {today.strftime('%Y-%m-%d')}: FULL SCAN TRIGGERED (Sunday/1st of Month)")
        else:
            print(f"📅 {today.strftime('%Y-%m-%d')}: DAILY SCAN (New movies only)")

        # --- 3. Per-source scraping with dedup tracking (Tasks 4.2 & 4.3) ---
        all_films = {}  # film_id -> {'film': dict, 'sources': set}
        combined_current_ids = set()
        films_to_scan_set = set()  # film_ids that need JustWatch scanning

        for source in sources:
            print(f"\n📂 Scraping source: {source['name']}")
            try:
                films = scrape_films(source['url'], pw_page=page)
            except Exception as e:
                print(f"⚠️ Failed to scrape {source['name']}: {e}")
                continue

            history = load_history(source['key'])
            source_ids = {f"{f['title']}_{f['year']}" for f in films}
            combined_current_ids.update(source_ids)

            # Track sources per film for deduplication and tagging
            for f in films:
                fid = f"{f['title']}_{f['year']}"
                if fid not in all_films:
                    all_films[fid] = {'film': f, 'sources': set()}
                all_films[fid]['sources'].add(source['name'])

            # Determine what to scan for this source
            if is_full_scan:
                for f in films:
                    films_to_scan_set.add(f"{f['title']}_{f['year']}")
            else:
                for f in films:
                    fid = f"{f['title']}_{f['year']}"
                    if fid not in history:
                        films_to_scan_set.add(fid)

            # Save history for this source
            save_history(source['key'], source_ids)

        # Build deduplicated films_to_scan list
        films_to_scan = [all_films[fid]['film'] for fid in films_to_scan_set if fid in all_films]

        # --- 4. Query JustWatch via API (all countries per movie in one call) ---
        new_rows = []

        if not films_to_scan:
            print("☕ No new movies to check for streaming offers.")
        else:
            print(f"🚀 Processing {len(films_to_scan)} movies across {len(COUNTRIES)} countries...")
            movie_cache = {}

            for film in films_to_scan:
                movie_id = f"{film['title']}_{film['year']}"

                if movie_id not in movie_cache:
                    poster, runtime = get_movie_metadata(film["title"], film["year"], TMDB_TOKEN)
                    movie_cache[movie_id] = {"poster_url": poster, "runtime": runtime}

                # Get localized title (use first non-English country for search hint)
                local_title = get_localized_title(film["title"], film["year"], COUNTRIES[0], TMDB_TOKEN)

                # Single API call gets offers for ALL countries
                offers_by_country = get_film_offers_api(
                    film["title"], film["year"], COUNTRIES, local_title=local_title
                )

                source_label = ", ".join(sorted(all_films[movie_id]['sources']))
                for country, providers in offers_by_country.items():
                    unique_cleaned = {clean_provider_name(p) for p in providers}
                    for provider in unique_cleaned:
                        new_rows.append({
                            "title": film["title"],
                            "year": film["year"],
                            "country": country.upper(),
                            "provider": provider,
                            "poster_url": movie_cache[movie_id]["poster_url"],
                            "runtime": movie_cache[movie_id]["runtime"],
                            "last_updated": today.strftime("%Y-%m-%d"),
                            "source": source_label,
                        })

                time.sleep(random.uniform(1.0, 2.0))

        browser.close()

    # --- 5. Pruning with combined multi-source IDs (Task 4.5) ---
    # Save snapshot of old CSV for alert comparison
    OLD_SNAPSHOT = DATA_DIR / "unwatched_by_country.old.csv"
    if OUTPUT_FILE.exists():
        import shutil
        shutil.copy2(OUTPUT_FILE, OLD_SNAPSHOT)

    if OUTPUT_FILE.exists():
        df_existing = pd.read_csv(OUTPUT_FILE)
        df_existing['temp_id'] = df_existing['title'] + "_" + df_existing['year'].astype(str)

        # PRUNE: Keep only rows where the movie still exists in any current source
        df_pruned = df_existing[df_existing['temp_id'].isin(combined_current_ids)].copy()
        df_pruned.drop(columns=['temp_id'], inplace=True)

        rows_removed = len(df_existing) - len(df_pruned)
        if rows_removed > 0:
            print(f"🧹 Pruned {rows_removed} rows for movies removed from Letterboxd.")
    else:
        df_pruned = pd.DataFrame()

    # --- 6. Save results ---
    if new_rows:
        df_new = pd.DataFrame(new_rows)
        if is_full_scan:
            # Full scan: Fresh start
            df_new.to_csv(OUTPUT_FILE, index=False)
        else:
            # Daily scan: Merge new findings with the pruned existing database
            combined_df = pd.concat([df_pruned, df_new]).drop_duplicates(
                subset=["title", "year", "country", "provider"], keep="last"
            )
            combined_df.to_csv(OUTPUT_FILE, index=False)
    else:
        # No new movies found — still save pruned version to reflect deletions
        df_pruned.to_csv(OUTPUT_FILE, index=False)

    print(f"✅ Sync complete. Results: {OUTPUT_FILE}")

    # --- 7. Check for new availability and send alerts ---
    if OLD_SNAPSHOT.exists():
        newly_available = find_new_availability(OLD_SNAPSHOT, OUTPUT_FILE)
        send_alert_email(newly_available)
        OLD_SNAPSHOT.unlink()  # Clean up snapshot

if __name__ == "__main__":
    main()

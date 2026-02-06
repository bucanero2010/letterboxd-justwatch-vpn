import json
import pandas as pd
import time
import random
from playwright.sync_api import sync_playwright
from letterbox_scraper import scrape_films
from matcher import get_unwatched
from justwatch_query import get_film_offers

# Load config
with open("config.json", "r") as f:
    config = json.load(f)

USERNAME = config["letterboxd_user"]
# Ensure countries are loaded from config
COUNTRIES = config.get("country_scan", ["US", "UK", "ES", "AR"])

def main():
    print(f"--- Fetching Letterboxd data for {USERNAME} ---")
    watched = scrape_films(f"https://letterboxd.com/{USERNAME}/films/")
    watchlist = scrape_films(f"https://letterboxd.com/{USERNAME}/watchlist/")
    unwatched = get_unwatched(watchlist, watched)
    print(f"Found {len(unwatched)} unwatched films to check.\n")

    rows = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Use a consistent context to build cookies/session history per country
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        # LOOP 1: By Country (External)
        for country in COUNTRIES:
            print(f"\n🌍 STARTING SCAN: {country.upper()}")
            print("=" * 30)
            
            # LOOP 2: By Movie (Internal)
            for film in unwatched:
                # Use the function as defined in justwatch_query
                offers = get_film_offers(page, film["title"], film["year"], country.lower())
                
                if offers:
                    for o in offers:
                        rows.append({
                            "title": film["title"],
                            "year": film["year"],
                            "country": country.upper(),
                            "provider": o
                        })
                
                # IMPORTANT: Human-like delay to prevent IP blocking
                # JustWatch is sensitive to rapid searches
                time.sleep(random.uniform(2, 4)*0.01)

            print(f"✅ Finished all films for {country.upper()}.")
            # Optional: Longer rest between switching countries
            time.sleep(5)

        browser.close()

    # Save results
    if rows:
        df = pd.DataFrame(rows)
        df.to_csv("data/unwatched_by_country.csv", index=False)
        df.to_json("data/unwatched_by_country.json", orient="records", indent=2)
        print(f"\n✅ Done! Results saved for {len(unwatched)} films across {len(COUNTRIES)} countries.")
    else:
        print("\n❌ No streaming results found.")

if __name__ == "__main__":
    main()
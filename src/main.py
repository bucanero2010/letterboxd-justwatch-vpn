import json
import pandas as pd
from playwright.sync_api import sync_playwright  # Using sync version
from letterbox_scraper import scrape_films
from matcher import get_unwatched
from justwatch_query import get_film_offers # Updated import

# Load config
with open("config.json", "r") as f:
    config = json.load(f)

USERNAME = config["letterboxd_user"]
COUNTRIES = config.get("country_scan", ["US"])

def main():
    # ... (Your existing Letterboxd scraping code remains the same) ...
    watched = scrape_films(f"https://letterboxd.com/{USERNAME}/films/")
    watchlist = scrape_films(f"https://letterboxd.com/{USERNAME}/watchlist/")
    unwatched = get_unwatched(watchlist, watched)

    rows = []

    # Start Playwright once
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        for film in unwatched:
            print(f"🔍 Checking: {film['title']} ({film['year']})")

            for country in COUNTRIES:
                # Use the new combined function
                offers = get_film_offers(page, film["title"], film["year"], country.lower())
                
                for o in offers:
                    rows.append({
                        "title": film["title"],
                        "year": film["year"],
                        "country": country,
                        "provider": o["provider"],
                        "monetization": o["monetization"],
                        "details": o["details"]
                    })

        browser.close()

    # Save results
    df = pd.DataFrame(rows)
    df.to_csv("data/unwatched.csv", index=False)
    print(f"✅ Results saved for {len(unwatched)} films")

if __name__ == "__main__":
    main()
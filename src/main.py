import json
import time
import random
from pathlib import Path

import pandas as pd
from playwright.sync_api import sync_playwright

# --- LOCAL MODULES ---
from letterbox_scraper import scrape_films
from matcher import get_unwatched
from justwatch_query import get_film_offers
from poster_service import get_poster_url

# --- PATHS ---
SCRIPT_DIR = Path(__file__).resolve().parent
BASE_DIR = SCRIPT_DIR.parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_FILE = DATA_DIR / "unwatched_by_country.csv"

DATA_DIR.mkdir(parents=True, exist_ok=True)


def load_config():
    for path in (SCRIPT_DIR / "config.json", BASE_DIR / "config.json"):
        if path.exists():
            with open(path, "r") as f:
                return json.load(f)
    raise FileNotFoundError("❌ config.json not found")


def main():
    config = load_config()

    USERNAME = config["letterboxd_user"]
    TMDB_TOKEN = config["tmdb_key"]
    COUNTRIES = config.get("country_scan", ["US"])

    print(f"\n🎞️ Fetching Letterboxd data for {USERNAME}")

    watched = scrape_films(f"https://letterboxd.com/{USERNAME}/films/by/date/")
    watchlist = scrape_films(f"https://letterboxd.com/{USERNAME}/watchlist/")
    unwatched = get_unwatched(watchlist, watched)

    print(f"🧮 Unwatched films: {len(unwatched)}")

    rows = []
    poster_cache = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            )
        )
        page = context.new_page()

        for country in COUNTRIES:
            country_code = country.lower()
            print(f"\n🌍 Scanning country: {country.upper()}")

            for film in unwatched:
                title = film["title"]
                year = film["year"]

                cache_key = f"{title}_{year}"

                # --- POSTER ---
                if cache_key not in poster_cache:
                    print(f"🖼️  Fetching poster: {title}")
                    poster_cache[cache_key] = get_poster_url(
                        title,
                        year,
                        TMDB_TOKEN
                    )

                # --- JUSTWATCH ---
                offers = get_film_offers(
                    page=page,
                    title=title,
                    year=year,
                    country=country_code,
                )

                if offers:
                    for provider in offers:
                        rows.append({
                            "title": title,
                            "year": year,
                            "country": country.upper(),
                            "provider": provider,
                            "poster_url": poster_cache[cache_key],
                        })

                time.sleep(random.uniform(1.0, 2.0))

        browser.close()

    if not rows:
        print("\n⚠️ No offers found.")
        return

    df = pd.DataFrame(rows)
    df.to_csv(OUTPUT_FILE, index=False)
    print(f"\n✅ Results saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()

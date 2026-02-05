import json
import pandas as pd
from letterbox import scrape_films
from matcher import get_unwatched
from justwatch import search_title, extract_offers, get_providers

# Load config
with open("config.json", "r") as f:
    config = json.load(f)

USERNAME = config["letterboxd_user"]
COUNTRIES = config.get("country_scan", ["ES"])

WATCHED_URL = f"https://letterboxd.com/{USERNAME}/films/"
WATCHLIST_URL = f"https://letterboxd.com/{USERNAME}/watchlist/"

def main():
    print(f"Scraping watched films for {USERNAME}...")
    watched = scrape_films(WATCHED_URL)

    print("Scraping watchlist...")
    watchlist = scrape_films(WATCHLIST_URL)

    unwatched = get_unwatched(watchlist, watched)
    print(f"Found {len(unwatched)} unwatched films")

    # Fetch provider mappings for all countries upfront
    providers_by_country = {c: get_providers(c) for c in COUNTRIES}

    rows = []

    for film in unwatched:
        print(f"🔍 {film['title']} ({film['year']})")

        for country in COUNTRIES:
            item = search_title(film["title"], year=film["year"], country=country)
            if not item:
                continue

            for o in extract_offers(item):
                provider_name = providers_by_country[country].get(
                    o["provider_id"], f"Unknown ({o['provider_id']})"
                )
                rows.append({
                    "title": film["title"],
                    "year": film["year"],
                    "country": country,
                    "provider": provider_name,
                    "monetization": o["monetization"]
                })

    df = pd.DataFrame(rows)
    df.to_csv("data/unwatched.csv", index=False)
    df.to_json("data/unwatched.json", orient="records", indent=2)

    print("✅ Results saved to data/unwatched.csv and data/unwatched.json")

if __name__ == "__main__":
    main()

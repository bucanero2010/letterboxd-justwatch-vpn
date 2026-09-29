"""
Export data/unwatched_by_country.csv to web/public/data.json for the Next.js frontend.

Run from anywhere: python src/export_web_data.py
"""

import csv
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
CSV_PATH = BASE_DIR / "data" / "unwatched_by_country.csv"
CONFIG_PATH = BASE_DIR / "src" / "config.json"
OUT_PATH = BASE_DIR / "web" / "public" / "data.json"


def main():
    movies = {}
    last_updated = ""
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            key = (row["title"], row["year"])
            movie = movies.setdefault(key, {
                "title": row["title"],
                "year": int(float(row["year"])) if row["year"] else None,
                "poster": row.get("poster_url") or None,
                "runtime": int(float(row["runtime"])) if row.get("runtime") else None,
                "offers": set(),
                "sources": set(),
            })
            movie["offers"].add((row["country"], row["provider"]))
            for s in (row.get("source") or "").split(","):
                if s.strip():
                    movie["sources"].add(s.strip())
            last_updated = max(last_updated, row.get("last_updated") or "")

    out_movies = [
        {
            **m,
            "offers": [{"c": c, "p": p} for c, p in sorted(m["offers"])],
            "sources": sorted(m["sources"]),
        }
        for m in movies.values()
    ]

    scan_countries = ["US"]
    if CONFIG_PATH.exists():
        scan_countries = json.loads(CONFIG_PATH.read_text()).get("country_scan", scan_countries)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps({
        "lastUpdated": last_updated,
        "scanCountries": scan_countries,
        "movies": out_movies,
    }, separators=(",", ":"), ensure_ascii=False))
    print(f"Wrote {len(out_movies)} movies to {OUT_PATH}")


if __name__ == "__main__":
    main()

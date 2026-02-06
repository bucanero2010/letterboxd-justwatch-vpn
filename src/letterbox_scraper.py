import time
import re
from urllib.parse import urljoin
import cloudscraper
from bs4 import BeautifulSoup

# Cloudflare-safe scraper with real browser fingerprint
scraper = cloudscraper.create_scraper(
    browser={
        "browser": "chrome",
        "platform": "darwin",
        "desktop": True,
    }
)

# Regex to extract year from title if present at the end
YEAR_RE = re.compile(r"\((\d{4})\)$")


def scrape_films(base_url, sleep=1, max_pages=100):
    """
    Scrape films from any Letterboxd paginated list using react-component metadata.
    Works for:
        - /films/
        - /films/by/date/
        - /watchlist/
        - /list/<slug>/

    Extracts:
        - title
        - slug
        - year (if available)
    """

    films = []
    seen_slugs = set()

    # Normalize URL (important for GitHub Actions)
    next_path = base_url.replace("https://letterboxd.com", "")

    # 🔑 Critical fix: avoid /films/ which returns 403 on CI
    if next_path.endswith("/films/"):
        next_path = next_path.replace("/films/", "/films/by/date/")

    page_count = 1

    while next_path and page_count <= max_pages:
        url = urljoin("https://letterboxd.com", next_path)
        print(f"Scraping: {url}")

        r = scraper.get(url)

        # Retry once with explicit headers if blocked
        if r.status_code == 403:
            print(f"⚠️ 403 detected, retrying with headers: {url}")
            r = scraper.get(
                url,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/122.0.0.0 Safari/537.36"
                    ),
                    "Accept-Language": "en-US,en;q=0.9",
                    "Referer": "https://letterboxd.com/",
                },
            )

        if r.status_code != 200:
            print(f"Failed to fetch {url}: {r.status_code}")
            break

        soup = BeautifulSoup(r.text, "html.parser")

        # React components contain movie metadata
        components = soup.find_all("div", class_="react-component")

        for comp in components:
            slug = comp.get("data-item-slug")
            title_raw = comp.get("data-item-name") or ""

            if not slug or slug in seen_slugs:
                continue

            # Extract year if present
            year_match = YEAR_RE.search(title_raw)
            year = int(year_match.group(1)) if year_match else None

            # Clean title
            title = YEAR_RE.sub("", title_raw).strip()

            films.append({
                "title": title,
                "year": year,
                "slug": slug
            })

            seen_slugs.add(slug)

        # Pagination
        next_link = soup.find("a", class_="next")
        next_path = next_link.get("href") if next_link else None

        page_count += 1
        time.sleep(sleep)

    return films

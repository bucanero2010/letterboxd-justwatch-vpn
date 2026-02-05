import time
import re
from urllib.parse import urljoin
import cloudscraper
from bs4 import BeautifulSoup

# Cloudflare-safe scraper
scraper = cloudscraper.create_scraper()

# Regex to extract year from title if present at the end
YEAR_RE = re.compile(r"\((\d{4})\)$")

def scrape_films(base_url, sleep=1, max_pages=100):
    """
    Scrape films from any Letterboxd paginated list using react-component metadata.
    Works for:
        - /films/
        - /watchlist/
        - /list/<slug>/
    Extracts:
        - title
        - slug
        - year (from title if available)
    """

    films = []
    seen_slugs = set()

    # Remove domain if present
    next_path = base_url.replace("https://letterboxd.com", "")

    page = 1
    while next_path and page <= max_pages:
        url = urljoin("https://letterboxd.com", next_path)
        print(f"Scraping: {url}")

        r = scraper.get(url)
        if r.status_code != 200:
            print(f"Failed to fetch {url}: {r.status_code}")
            break

        soup = BeautifulSoup(r.text, "html.parser")

        # All React components containing films
        components = soup.find_all("div", class_="react-component")

        for comp in components:
            slug = comp.get("data-item-slug")
            title_raw = comp.get("data-item-name") or ""

            if not slug or slug in seen_slugs:
                continue

            # Extract year from title
            year_match = YEAR_RE.search(title_raw)
            year = int(year_match.group(1)) if year_match else None

            # Remove year from title
            title = YEAR_RE.sub("", title_raw).strip()

            films.append({
                "title": title,
                "year": year,
                "slug": slug
            })
            seen_slugs.add(slug)

        # Pagination: next page
        next_link = soup.find("a", class_="next")
        next_path = next_link.get("href") if next_link else None

        page += 1
        time.sleep(sleep)

    return films

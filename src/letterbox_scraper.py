import logging
import time
import re
from urllib.parse import urljoin
import cloudscraper
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

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


def discover_lists(username: str, sleep_time: float = 1, max_pages: int = 10) -> list:
    """
    Scrape the user's Letterboxd lists page to discover all personal lists.

    Args:
        username: Letterboxd username
        sleep_time: Delay between page requests
        max_pages: Maximum pages to paginate through

    Returns:
        List of dicts with keys: 'name' (str), 'url' (str), 'slug' (str)
        Example: [{'name': 'Top 50 Sci-Fi', 'url': '/bucanero2010/list/top-50-sci-fi/', 'slug': 'top-50-sci-fi'}]
    """
    lists = []
    seen_slugs = set()
    next_path = f"/{username}/lists/"

    page = 1
    while next_path and page <= max_pages:
        url = urljoin("https://letterboxd.com", next_path)
        logger.info(f"Discovering lists: {url}")

        try:
            r = scraper.get(url)
        except Exception as e:
            logger.warning(f"Failed to reach {url}: {e}")
            return []

        if r.status_code != 200:
            logger.warning(f"Failed to fetch {url}: HTTP {r.status_code}")
            return []

        soup = BeautifulSoup(r.text, "html.parser")

        # Each list on the page has a link matching /{username}/list/{slug}/
        list_pattern = re.compile(rf"^/{re.escape(username)}/list/([^/]+)/$")

        for link in soup.find_all("a", href=list_pattern):
            href = link.get("href", "")
            match = list_pattern.match(href)
            if not match:
                continue

            slug = match.group(1)
            if slug in seen_slugs:
                continue

            # Extract the list name from the link text
            name = link.get_text(strip=True)
            if not name:
                continue

            lists.append({
                "name": name,
                "url": href,
                "slug": slug,
            })
            seen_slugs.add(slug)

        # Pagination: follow "next" link
        next_link = soup.find("a", class_="next")
        next_path = next_link.get("href") if next_link else None

        page += 1
        time.sleep(sleep_time)

    if not lists:
        logger.info(f"No lists found for user '{username}'.")

    return lists

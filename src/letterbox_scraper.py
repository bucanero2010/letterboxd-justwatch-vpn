import logging
import time
import re
from urllib.parse import urljoin
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Regex to extract year from title if present at the end
YEAR_RE = re.compile(r"\((\d{4})\)$")


def _get_page_html(url: str, pw_page=None) -> str | None:
    """Fetch page HTML using Playwright if available, else cloudscraper."""
    if pw_page:
        try:
            pw_page.goto(url, wait_until="domcontentloaded", timeout=15000)
            return pw_page.content()
        except Exception as e:
            logger.warning(f"Playwright failed for {url}: {e}")
            return None
    else:
        import cloudscraper
        scraper = cloudscraper.create_scraper()
        r = scraper.get(url)
        if r.status_code != 200:
            logger.warning(f"Failed to fetch {url}: HTTP {r.status_code}")
            return None
        return r.text


def scrape_films(base_url, pw_page=None, sleep=1, max_pages=100):
    """
    Scrape films from any Letterboxd paginated list using react-component metadata.
    Works for /films/, /watchlist/, /list/<slug>/
    
    Args:
        base_url: Letterboxd list URL
        pw_page: Optional Playwright page for browser-based fetching
        sleep: Delay between pages
        max_pages: Max pages to paginate
    """
    films = []
    seen_slugs = set()
    next_path = base_url.replace("https://letterboxd.com", "")

    page = 1
    while next_path and page <= max_pages:
        url = urljoin("https://letterboxd.com", next_path)
        print(f"Scraping: {url}")

        html = _get_page_html(url, pw_page)
        if not html:
            print(f"Failed to fetch {url}")
            break

        soup = BeautifulSoup(html, "html.parser")

        components = soup.find_all("div", class_="react-component")
        for comp in components:
            slug = comp.get("data-item-slug")
            title_raw = comp.get("data-item-name") or ""

            if not slug or slug in seen_slugs:
                continue

            year_match = YEAR_RE.search(title_raw)
            year = int(year_match.group(1)) if year_match else None
            title = YEAR_RE.sub("", title_raw).strip()

            films.append({"title": title, "year": year, "slug": slug})
            seen_slugs.add(slug)

        next_link = soup.find("a", class_="next")
        next_path = next_link.get("href") if next_link else None

        page += 1
        time.sleep(sleep)

    return films


def discover_lists(username: str, pw_page=None, sleep_time: float = 1, max_pages: int = 10) -> list:
    """
    Scrape the user's Letterboxd lists page to discover all personal lists.

    Args:
        username: Letterboxd username
        pw_page: Optional Playwright page for browser-based fetching
        sleep_time: Delay between page requests
        max_pages: Maximum pages to paginate through

    Returns:
        List of dicts with keys: 'name' (str), 'url' (str), 'slug' (str)
    """
    lists = []
    seen_slugs = set()
    next_path = f"/{username}/lists/"

    page = 1
    while next_path and page <= max_pages:
        url = urljoin("https://letterboxd.com", next_path)
        logger.info(f"Discovering lists: {url}")

        html = _get_page_html(url, pw_page)
        if not html:
            logger.warning(f"Failed to fetch {url}")
            return lists

        soup = BeautifulSoup(html, "html.parser")

        list_pattern = re.compile(rf"^/{re.escape(username)}/list/([^/]+)/$")

        # Only match links inside <h2> tags to get the actual list name,
        # not poster overlay links which may contain film titles
        for h2 in soup.find_all("h2", class_="name"):
            link = h2.find("a", href=list_pattern)
            if not link:
                continue

            href = link.get("href", "")
            match = list_pattern.match(href)
            if not match:
                continue

            slug = match.group(1)
            if slug in seen_slugs:
                continue

            name = link.get_text(strip=True)
            if not name:
                continue

            lists.append({"name": name, "url": href, "slug": slug})
            seen_slugs.add(slug)

        next_link = soup.find("a", class_="next")
        next_path = next_link.get("href") if next_link else None

        page += 1
        time.sleep(sleep_time)

    if not lists:
        logger.info(f"No lists found for user '{username}'.")

    return lists

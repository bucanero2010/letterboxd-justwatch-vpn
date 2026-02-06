import time
import re
import random
from bs4 import BeautifulSoup

YEAR_RE = re.compile(r"\((\d{4})\)$")

def scrape_films_browser(page, base_url, max_pages=100):
    films = []
    seen_slugs = set()
    next_path = base_url.replace("https://letterboxd.com", "")

    # Apply stealth script to hide automation flags
    page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
    """)

    page_num = 1
    while next_path and page_num <= max_pages:
        url = f"https://letterboxd.com{next_path}"
        print(f"🚀 [Browser] Scraping: {url}")

        try:
            # Human-like pause
            time.sleep(random.uniform(2, 4)) 

            # Capture the response object from page.goto
            response = page.goto(url, wait_until="domcontentloaded", timeout=60000)

            # Check for 403 specifically using the captured response
            if response and response.status == 403:
                print(f"❌ Blocked (403) on {url}. Saving debug screenshot...")
                page.screenshot(path="debug_403.png")
                break
                
            # Simulate human interaction to satisfy Cloudflare
            page.mouse.move(random.randint(0, 100), random.randint(0, 100))
            page.evaluate("window.scrollTo(0, document.body.scrollHeight / 3)")
            time.sleep(1)

            # Extract HTML
            content = page.content()
            soup = BeautifulSoup(content, "html.parser")
            
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

            # Find next page
            next_link = soup.find("a", class_="next")
            next_path = next_link.get("href") if next_link else None
            page_num += 1

        except Exception as e:
            print(f"⚠️ Error scraping {url}: {e}")
            break

    return films
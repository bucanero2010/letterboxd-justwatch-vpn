import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

def scrape_films(list_url, max_pages=50):
    films = []
    page = 1

    while page <= max_pages:
        url = f"{list_url}page/{page}/"
        r = requests.get(url)

        if r.status_code != 200:
            break

        soup = BeautifulSoup(r.text, "html.parser")
        posters = soup.select("li.poster-container")

        if not posters:
            break

        for p in posters:
            img = p.select_one("img")
            title = img["alt"].strip()

            year_tag = p.select_one("span.year")
            year = int(year_tag.text) if year_tag else None

            film_slug = p.select_one("div.poster")["data-film-slug"]

            films.append({
                "title": title,
                "year": year,
                "slug": film_slug
            })

        page += 1

    return films

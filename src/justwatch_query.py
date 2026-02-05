from bs4 import BeautifulSoup
import requests
import urllib.parse

film_title = "Gone with the Wind"
country = "us"
url = f"https://www.justwatch.com/{country}/search?q={urllib.parse.quote(film_title)}"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/144.0.0.0 Safari/537.36"
}

r = requests.get(url, headers=headers)
soup = BeautifulSoup(r.text, "html.parser")

# Extract all movie links
links = soup.find_all("a", href=True)
movie_links = [a['href'] for a in links if "/movie/" in a['href']]

print(f"Found {len(movie_links)} movie links. First 5:")

for l in movie_links[:5]:
    print("-", l)
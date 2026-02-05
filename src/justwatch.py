import requests

JW_SEARCH_URL = "https://apis.justwatch.com/content/titles/{country}/popular"

def search_title(title, year=None, country="PT"):
    """
    Search for a movie title in JustWatch and optionally filter by year.
    """
    payload = {
        "query": title,
        "page_size": 5,
        "page": 1,
        "content_types": ["movie"]
    }

    r = requests.post(
        JW_SEARCH_URL.format(country=country),
        json=payload,
        headers={"Content-Type": "application/json",
                 "User-Agent": "Mozilla/5.0"}
    )

    if r.status_code != 200:
        return None

    items = r.json().get("items", [])

    # Simple match: prefer exact year match if provided
    for item in items:
        if year and item.get("original_release_year") != year:
            continue
        return item

    return None


def extract_offers(item):
    """
    Extract offers from a JustWatch item.
    Returns a list of dictionaries with provider_id and monetization_type.
    """
    offers = item.get("offers", [])
    results = []

    for o in offers:
        results.append({
            "provider_id": o.get("provider_id"),
            "monetization": o.get("monetization_type")
        })

    return results


def get_providers(country="PT"):
    """
    Get a mapping of JustWatch provider IDs to human-readable names for a country.
    """
    url = f"https://apis.justwatch.com/content/providers/{country}"
    r = requests.get(url)
    if r.status_code != 200:
        return {}
    providers = r.json()
    return {p["id"]: p["clear_name"] for p in providers}

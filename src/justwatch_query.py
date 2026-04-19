"""
JustWatch query module using the GraphQL API via simple-justwatch-python-api.
Replaces the previous Playwright-based scraping approach for much faster lookups.
"""

import re
import unicodedata
from simplejustwatchapi import search, offers_for_countries


def normalize(text):
    """Lowercase, strip accents, remove punctuation for fuzzy comparison."""
    text = unicodedata.normalize('NFD', text.lower())
    text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
    text = re.sub(r'[^\w\s]', '', text)
    return text.strip()


def validate_match(target_title, target_year, found_title, found_year):
    """Check if a search result matches the target movie."""
    if found_year is None or abs(target_year - found_year) > 1:
        return False
    target_words = set(normalize(target_title).split())
    found_words = set(normalize(found_title).split())
    stopwords = {'the', 'a', 'an', 'of', 'in', 'on', 'at', 'to', 'and', 'or',
                 'el', 'la', 'los', 'las', 'de', 'del', 'en', 'un', 'una', 'y',
                 'le', 'les', 'des', 'du', 'et', 'der', 'die', 'das', 'und'}
    significant = {w for w in target_words if len(w) > 2 and w not in stopwords}
    if not significant:
        significant = target_words
    matched = sum(1 for w in significant if w in found_words)
    if len(significant) <= 2:
        return matched >= len(significant)
    return matched >= max(2, len(significant) // 2)


def find_movie_id(title, year, local_title=None):
    """
    Search JustWatch for a movie and return its node ID.
    Tries localized title first, then English title.
    """
    target_year = int(year)

    # Try localized title first
    if local_title and local_title.lower() != title.lower():
        try:
            results = search(local_title, country="US", language="en", count=5)
            for r in results:
                if r.object_type == "MOVIE" and validate_match(local_title, target_year, r.title, r.release_year):
                    print(f"   ✅ Found: {r.title} ({r.release_year}) [id={r.entry_id}]")
                    return r.entry_id
        except Exception:
            pass

    # Fall back to English title
    try:
        print(f"   🔎 Searching for: '{title} ({year})'...")
        results = search(title, country="US", language="en", count=5)
        for r in results:
            if r.object_type == "MOVIE" and validate_match(title, target_year, r.title, r.release_year):
                print(f"   ✅ Found: {r.title} ({r.release_year}) [id={r.entry_id}]")
                return r.entry_id
    except Exception as e:
        print(f"   ⚠️ Search error: {e}")

    return None


def get_streaming_offers(node_id, countries):
    """
    Get streaming offers for a movie across multiple countries in one API call.
    Returns dict: {country_code: [provider_name, ...]}
    """
    try:
        all_offers = offers_for_countries(node_id, countries)
    except Exception as e:
        print(f"   ⚠️ Offers error: {e}")
        return {}

    result = {}
    for country, country_offers in all_offers.items():
        streaming = [
            o for o in country_offers
            if o.monetization_type in ('FLATRATE', 'FREE', 'ADS')
        ]
        if streaming:
            providers = list({o.package.name for o in streaming})
            result[country] = providers

    return result


def get_film_offers_api(title, year, countries, local_title=None):
    """
    High-level function: find a movie and get streaming offers for all countries.
    Returns dict: {country_code: [provider_name, ...]}
    """
    try:
        target_year = int(year)
    except (TypeError, ValueError):
        return {}

    node_id = find_movie_id(title, target_year, local_title=local_title)
    if not node_id:
        return {}

    offers = get_streaming_offers(node_id, [c.upper() for c in countries])

    if offers:
        for country, providers in offers.items():
            print(f"   🎉 {country}: {', '.join(sorted(providers))}")

    return offers

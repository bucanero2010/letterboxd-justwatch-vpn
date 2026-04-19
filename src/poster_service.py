import requests

TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w500"

def get_movie_metadata(title, year, api_token):
    """
    Fetch poster + runtime from TMDB.
    Returns: (poster_url, runtime)
    """
    search_url = "https://api.themoviedb.org/3/search/movie"
    headers = {
        "accept": "application/json",
        "Authorization": f"Bearer {api_token}"
    }

    params = {
        "query": title,
        "year": year,
        "language": "en-US"
    }

    try:
        search = requests.get(search_url, headers=headers, params=params)
        search.raise_for_status()
        data = search.json()

        if not data.get("results"):
            raise ValueError("No TMDB results")

        movie = data["results"][0]
        movie_id = movie["id"]
        poster_path = movie.get("poster_path")

        # --- SECOND CALL: movie details ---
        details_url = f"https://api.themoviedb.org/3/movie/{movie_id}"
        details = requests.get(details_url, headers=headers)
        details.raise_for_status()
        details_data = details.json()

        runtime = details_data.get("runtime")

        poster_url = (
            f"{TMDB_IMAGE_BASE}{poster_path}"
            if poster_path
            else "https://via.placeholder.com/500x750?text=No+Poster"
        )

        return poster_url, runtime

    except Exception as e:
        print(f"⚠️ TMDB error for {title}: {e}")
        return (
            "https://via.placeholder.com/500x750?text=No+Poster",
            None
        )


# TMDB country code mapping (JustWatch country -> TMDB ISO 3166-1)
COUNTRY_TO_TMDB = {
    "us": "US", "uk": "GB", "ca": "CA", "au": "AU",
    "dk": "DK", "za": "ZA", "es": "ES", "ar": "AR", "jp": "JP",
    "pe": "PE", "mx": "MX", "br": "BR", "fr": "FR", "de": "DE",
    "it": "IT", "kr": "KR", "in": "IN", "se": "SE", "no": "NO",
}

# TMDB language codes for localized search
COUNTRY_TO_LANG = {
    "us": "en-US", "uk": "en-GB", "ca": "en-CA", "au": "en-AU",
    "dk": "da-DK", "za": "en-ZA", "es": "es-ES", "ar": "es-AR",
    "jp": "ja-JP", "pe": "es-PE", "mx": "es-MX", "br": "pt-BR",
    "fr": "fr-FR", "de": "de-DE", "it": "it-IT", "kr": "ko-KR",
    "in": "hi-IN", "se": "sv-SE", "no": "nb-NO",
}


def get_localized_title(title, year, country, api_token):
    """
    Get the localized movie title for a given country using TMDB.
    Returns the localized title, or the original title if not found.
    """
    headers = {
        "accept": "application/json",
        "Authorization": f"Bearer {api_token}"
    }

    # First, find the movie on TMDB
    search_url = "https://api.themoviedb.org/3/search/movie"
    params = {"query": title, "year": year, "language": "en-US"}

    try:
        search = requests.get(search_url, headers=headers, params=params)
        search.raise_for_status()
        data = search.json()

        if not data.get("results"):
            return title

        movie_id = data["results"][0]["id"]

        # Try localized title via translations
        lang = COUNTRY_TO_LANG.get(country.lower())
        if lang:
            details_url = f"https://api.themoviedb.org/3/movie/{movie_id}"
            details = requests.get(details_url, headers=headers, params={"language": lang})
            details.raise_for_status()
            localized = details.json().get("title")
            if localized and localized.lower() != title.lower():
                return localized

        return title

    except Exception:
        return title

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

"""TMDB Metadata Fetcher module for the Hybrid Movie Recommender.

Fetches and caches TMDB metadata (genres, directors, cast, keywords, plot overview)
for any set of TMDB IDs. Handles rate-limiting with exponential backoff.
Provides candidate movie discovery via TMDB discover endpoints.
"""

import json
import logging
import time
from dataclasses import dataclass, asdict
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

TMDB_BASE_URL = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w500"


@dataclass
class MovieMetadata:
    """Metadata for a single movie fetched from TMDB."""

    tmdb_id: int
    title: str
    year: int
    genres: list[str]
    directors: list[str]
    cast: list[str]          # top 5 billed
    keywords: list[str]
    overview: str             # plot text
    poster_path: str | None
    runtime: int | None


class TMDBMetadataFetcher:
    """Fetches and caches TMDB metadata for movies.

    Uses the TMDB v3 API with Bearer token authentication.
    Implements rate-limit handling with exponential backoff.
    """

    def __init__(self, api_token: str, cache_path: Path):
        """Initialize with TMDB bearer token and cache file path.

        Args:
            api_token: TMDB API bearer token for authentication.
            cache_path: Path to the JSON cache file for metadata persistence.
        """
        self.api_token = api_token
        self.cache_path = Path(cache_path)
        self.headers = {
            "accept": "application/json",
            "Authorization": f"Bearer {api_token}",
        }
        self._cache: dict[int, MovieMetadata] = {}
        self._load_cache()

    def _load_cache(self) -> None:
        """Load metadata cache from disk if it exists."""
        if self.cache_path.exists():
            try:
                with open(self.cache_path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                for tmdb_id_str, fields in raw.items():
                    tmdb_id = int(tmdb_id_str)
                    self._cache[tmdb_id] = MovieMetadata(
                        tmdb_id=fields["tmdb_id"],
                        title=fields["title"],
                        year=fields["year"],
                        genres=fields["genres"],
                        directors=fields["directors"],
                        cast=fields["cast"],
                        keywords=fields["keywords"],
                        overview=fields["overview"],
                        poster_path=fields.get("poster_path"),
                        runtime=fields.get("runtime"),
                    )
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                logger.warning(f"Corrupt metadata cache, starting fresh: {e}")
                self._cache = {}

    def _request_with_retry(self, url: str, params: dict | None = None) -> dict | None:
        """Make an API request with exponential backoff on rate limits.

        Retries up to 3 times on HTTP 429 with delays of 1s, 2s, 4s.
        Returns the JSON response or None on failure.
        """
        max_retries = 3
        backoff_seconds = 1

        for attempt in range(max_retries + 1):
            try:
                response = requests.get(
                    url, headers=self.headers, params=params, timeout=15
                )

                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 429:
                    if attempt < max_retries:
                        logger.warning(
                            f"Rate limited (429), retrying in {backoff_seconds}s "
                            f"(attempt {attempt + 1}/{max_retries})"
                        )
                        time.sleep(backoff_seconds)
                        backoff_seconds *= 2
                    else:
                        logger.error(
                            f"Rate limited after {max_retries} retries, skipping: {url}"
                        )
                        return None
                elif response.status_code == 404:
                    logger.warning(f"TMDB resource not found (404): {url}")
                    return None
                else:
                    logger.warning(
                        f"TMDB API error {response.status_code} for {url}"
                    )
                    return None

            except requests.exceptions.Timeout:
                if attempt < max_retries:
                    logger.warning(
                        f"Request timeout, retrying in {backoff_seconds}s "
                        f"(attempt {attempt + 1}/{max_retries})"
                    )
                    time.sleep(backoff_seconds)
                    backoff_seconds *= 2
                else:
                    logger.error(f"Request timeout after {max_retries} retries: {url}")
                    return None
            except requests.exceptions.RequestException as e:
                logger.error(f"Request failed for {url}: {e}")
                return None

        return None

    def fetch_movie(self, tmdb_id: int) -> MovieMetadata | None:
        """Fetch full metadata for a single TMDB ID. Returns cached if available.

        Makes 3 API calls:
        - /movie/{id} for details (title, year, genres, overview, poster, runtime)
        - /movie/{id}/credits for directors and top 5 cast
        - /movie/{id}/keywords for keywords

        Args:
            tmdb_id: The TMDB movie ID to fetch.

        Returns:
            MovieMetadata object or None if the movie cannot be fetched.
        """
        # Return cached if available
        if tmdb_id in self._cache:
            return self._cache[tmdb_id]

        # Fetch movie details
        details_url = f"{TMDB_BASE_URL}/movie/{tmdb_id}"
        details = self._request_with_retry(details_url)
        if not details:
            return None

        # Fetch credits (directors + cast)
        credits_url = f"{TMDB_BASE_URL}/movie/{tmdb_id}/credits"
        credits_data = self._request_with_retry(credits_url)

        # Fetch keywords
        keywords_url = f"{TMDB_BASE_URL}/movie/{tmdb_id}/keywords"
        keywords_data = self._request_with_retry(keywords_url)

        # Parse details
        title = details.get("title", "")
        release_date = details.get("release_date", "")
        year = int(release_date[:4]) if release_date and len(release_date) >= 4 else 0
        genres = [g["name"] for g in details.get("genres", [])]
        overview = details.get("overview", "")
        poster_path = details.get("poster_path")
        runtime = details.get("runtime")

        # Parse credits
        directors = []
        cast = []
        if credits_data:
            crew = credits_data.get("crew", [])
            directors = [
                person["name"]
                for person in crew
                if person.get("job") == "Director"
            ]
            cast_list = credits_data.get("cast", [])
            cast = [person["name"] for person in cast_list[:5]]

        # Parse keywords
        keywords = []
        if keywords_data:
            keywords = [
                kw["name"] for kw in keywords_data.get("keywords", [])
            ]

        metadata = MovieMetadata(
            tmdb_id=tmdb_id,
            title=title,
            year=year,
            genres=genres,
            directors=directors,
            cast=cast,
            keywords=keywords,
            overview=overview,
            poster_path=poster_path,
            runtime=runtime,
        )

        self._cache[tmdb_id] = metadata
        return metadata

    def fetch_batch(
        self, tmdb_ids: list[int], progress_callback=None, save_every: int = 100
    ) -> dict[int, MovieMetadata]:
        """Fetch metadata for a batch of TMDB IDs with rate-limit handling.

        Saves the cache to disk every `save_every` movies to prevent data loss
        if the process is interrupted.

        Args:
            tmdb_ids: List of TMDB movie IDs to fetch.
            progress_callback: Optional callable(current, total) for progress updates.
            save_every: Save cache to disk every N movies (default 100).

        Returns:
            Dictionary mapping tmdb_id to MovieMetadata for successfully fetched movies.
        """
        results: dict[int, MovieMetadata] = {}
        total = len(tmdb_ids)
        fetched_since_save = 0

        for i, tmdb_id in enumerate(tmdb_ids):
            was_cached = tmdb_id in self._cache
            metadata = self.fetch_movie(tmdb_id)
            if metadata:
                results[tmdb_id] = metadata

            if not was_cached and metadata:
                fetched_since_save += 1

            # Periodically save cache to disk
            if fetched_since_save >= save_every:
                self.save_cache()
                fetched_since_save = 0

            if progress_callback:
                progress_callback(i + 1, total)

        # Final save
        self.save_cache()
        return results

    def fetch_candidates(
        self, genre_ids: list[int], min_pages: int = 250
    ) -> list[MovieMetadata]:
        """Fetch candidate movies from TMDB discover endpoints.

        Uses popular, top-rated, and genre-based discovery to build a broad
        candidate pool targeting 5,000+ movies.

        Args:
            genre_ids: List of TMDB genre IDs to include in genre-based discovery.
            min_pages: Minimum number of pages to fetch across all strategies.

        Returns:
            List of MovieMetadata objects for discovered candidates.
        """
        discovered_ids: set[int] = set()
        candidates: list[MovieMetadata] = []

        # Distribute pages across strategies
        pages_per_strategy = max(1, min_pages // (2 + len(genre_ids))) if genre_ids else max(1, min_pages // 2)

        # Strategy 1: Popular movies
        self._discover_movies(
            sort_by="popularity.desc",
            genre_id=None,
            max_pages=pages_per_strategy,
            discovered_ids=discovered_ids,
            candidates=candidates,
        )

        # Strategy 2: Top-rated movies
        self._discover_movies(
            sort_by="vote_average.desc",
            genre_id=None,
            max_pages=pages_per_strategy,
            discovered_ids=discovered_ids,
            candidates=candidates,
            extra_params={"vote_count.gte": 100},
        )

        # Strategy 3: Genre-based discovery
        if genre_ids:
            genre_pages = max(1, (min_pages - 2 * pages_per_strategy) // len(genre_ids))
            for genre_id in genre_ids:
                self._discover_movies(
                    sort_by="popularity.desc",
                    genre_id=genre_id,
                    max_pages=genre_pages,
                    discovered_ids=discovered_ids,
                    candidates=candidates,
                )

        if len(candidates) < 1000:
            logger.warning(
                f"Candidate pool contains only {len(candidates)} movies "
                f"(target: 5,000+). Limited candidate coverage."
            )

        return candidates

    def _discover_movies(
        self,
        sort_by: str,
        genre_id: int | None,
        max_pages: int,
        discovered_ids: set[int],
        candidates: list[MovieMetadata],
        extra_params: dict | None = None,
    ) -> None:
        """Fetch movies from the TMDB discover endpoint.

        Args:
            sort_by: Sort order for discovery (e.g., 'popularity.desc').
            genre_id: Optional genre ID to filter by.
            max_pages: Maximum number of pages to fetch.
            discovered_ids: Set of already-discovered TMDB IDs (modified in place).
            candidates: List of candidates to append to (modified in place).
            extra_params: Additional query parameters for the discover endpoint.
        """
        discover_url = f"{TMDB_BASE_URL}/discover/movie"

        for page in range(1, max_pages + 1):
            params = {
                "sort_by": sort_by,
                "page": page,
                "language": "en-US",
                "include_adult": "false",
            }
            if genre_id is not None:
                params["with_genres"] = str(genre_id)
            if extra_params:
                params.update(extra_params)

            data = self._request_with_retry(discover_url, params=params)
            if not data:
                break

            results = data.get("results", [])
            if not results:
                break

            for movie in results:
                movie_id = movie.get("id")
                if movie_id and movie_id not in discovered_ids:
                    discovered_ids.add(movie_id)

                    # Build a basic MovieMetadata from discover results
                    release_date = movie.get("release_date", "")
                    year = (
                        int(release_date[:4])
                        if release_date and len(release_date) >= 4
                        else 0
                    )

                    # Check if we already have full metadata cached
                    if movie_id in self._cache:
                        candidates.append(self._cache[movie_id])
                    else:
                        # Create partial metadata from discover data
                        # (genres come as IDs in discover, not names)
                        metadata = MovieMetadata(
                            tmdb_id=movie_id,
                            title=movie.get("title", ""),
                            year=year,
                            genres=[],  # Will be enriched later via fetch_movie
                            directors=[],
                            cast=[],
                            keywords=[],
                            overview=movie.get("overview", ""),
                            poster_path=movie.get("poster_path"),
                            runtime=None,
                        )
                        self._cache[movie_id] = metadata
                        candidates.append(metadata)

            # Respect TMDB's total_pages limit
            total_pages = data.get("total_pages", 1)
            if page >= total_pages:
                break

    def save_cache(self) -> None:
        """Persist metadata cache to disk as JSON.

        The cache maps tmdb_id (as string key) to serialized MovieMetadata fields.
        """
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)

        serialized = {}
        for tmdb_id, metadata in self._cache.items():
            serialized[str(tmdb_id)] = asdict(metadata)

        try:
            with open(self.cache_path, "w", encoding="utf-8") as f:
                json.dump(serialized, f, ensure_ascii=False, indent=2)
        except OSError as e:
            logger.warning(f"Failed to save metadata cache: {e}")

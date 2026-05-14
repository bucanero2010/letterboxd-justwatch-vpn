"""ID Mapper module for the Hybrid Movie Recommender.

Maps between Letterboxd slugs, TMDB IDs, and MovieLens IDs.
Loads MovieLens links.csv for TMDB ↔ MovieLens ID mapping.
Caches resolved TMDB IDs to minimize API calls across sessions.
"""

import csv
import json
import logging
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger(__name__)

TMDB_SEARCH_URL = "https://api.themoviedb.org/3/search/movie"


class IDMapper:
    """Maps between Letterboxd slugs, TMDB IDs, and MovieLens IDs."""

    def __init__(self, tmdb_token: str, cache_dir: Path):
        """Load MovieLens links.csv and TMDB ID cache.

        Args:
            tmdb_token: TMDB API bearer token for authentication.
            cache_dir: Path to the data directory containing caches and MovieLens data.
        """
        self._tmdb_token = tmdb_token
        self._cache_dir = Path(cache_dir)
        self._cache_path = self._cache_dir / "tmdb_id_cache.json"
        self._links_path = self._cache_dir / "ml-25m" / "links.csv"

        # Bidirectional mappings from links.csv
        self._tmdb_to_movielens: dict[int, int] = {}
        self._movielens_to_tmdb: dict[int, int] = {}

        # TMDB ID cache: slug -> tmdb_id
        self._slug_cache: dict[str, int] = {}

        self._load_links()
        self._load_cache()

    def _load_links(self) -> None:
        """Load MovieLens links.csv to build TMDB ↔ MovieLens ID mappings."""
        if not self._links_path.exists():
            logger.warning(
                "MovieLens links.csv not found at %s. "
                "TMDB ↔ MovieLens ID mapping will be unavailable until the dataset is downloaded.",
                self._links_path,
            )
            return

        try:
            with open(self._links_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    movielens_id = int(row["movieId"])
                    tmdb_id_str = row.get("tmdbId", "").strip()
                    if tmdb_id_str:
                        tmdb_id = int(tmdb_id_str)
                        self._tmdb_to_movielens[tmdb_id] = movielens_id
                        self._movielens_to_tmdb[movielens_id] = tmdb_id

            logger.info(
                "Loaded %d TMDB ↔ MovieLens ID mappings from links.csv.",
                len(self._tmdb_to_movielens),
            )
        except Exception as e:
            logger.warning("Failed to load links.csv: %s", e)

    def _load_cache(self) -> None:
        """Load the TMDB ID cache from disk."""
        if not self._cache_path.exists():
            logger.info("No existing TMDB ID cache found. Starting with empty cache.")
            return

        try:
            with open(self._cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Ensure values are integers
            self._slug_cache = {slug: int(tmdb_id) for slug, tmdb_id in data.items()}
            logger.info("Loaded %d cached TMDB ID mappings.", len(self._slug_cache))
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning("Corrupt TMDB ID cache at %s: %s. Starting fresh.", self._cache_path, e)
            self._slug_cache = {}

    def resolve_slug_to_tmdb_id(self, slug: str, title: str, year: int) -> Optional[int]:
        """Resolve a Letterboxd slug to a TMDB ID via TMDB search. Caches results.

        Args:
            slug: The Letterboxd film slug (used as cache key).
            title: The film title for TMDB search.
            year: The film release year for TMDB search.

        Returns:
            The TMDB ID if found, or None if unresolvable.
        """
        # Check cache first
        if slug in self._slug_cache:
            return self._slug_cache[slug]

        # Query TMDB search API
        headers = {
            "accept": "application/json",
            "Authorization": f"Bearer {self._tmdb_token}",
        }
        params = {
            "query": title,
            "year": year,
            "language": "en-US",
        }

        try:
            response = requests.get(TMDB_SEARCH_URL, headers=headers, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()

            results = data.get("results")
            if not results:
                logger.warning(
                    "No TMDB results for slug='%s' (title='%s', year=%d). Film will be excluded.",
                    slug,
                    title,
                    year,
                )
                return None

            tmdb_id = int(results[0]["id"])
            self._slug_cache[slug] = tmdb_id
            return tmdb_id

        except requests.RequestException as e:
            logger.warning(
                "TMDB API error resolving slug='%s' (title='%s', year=%d): %s",
                slug,
                title,
                year,
                e,
            )
            return None

    def tmdb_id_to_movielens_id(self, tmdb_id: int) -> Optional[int]:
        """Look up MovieLens ID from TMDB ID using links.csv.

        Args:
            tmdb_id: The TMDB movie ID.

        Returns:
            The MovieLens ID if found, or None if no mapping exists.
        """
        result = self._tmdb_to_movielens.get(tmdb_id)
        if result is None:
            logger.warning("No MovieLens ID found for TMDB ID %d.", tmdb_id)
        return result

    def movielens_id_to_tmdb_id(self, movielens_id: int) -> Optional[int]:
        """Reverse lookup: MovieLens ID → TMDB ID.

        Args:
            movielens_id: The MovieLens movie ID.

        Returns:
            The TMDB ID if found, or None if no mapping exists.
        """
        result = self._movielens_to_tmdb.get(movielens_id)
        if result is None:
            logger.warning("No TMDB ID found for MovieLens ID %d.", movielens_id)
        return result

    def save_cache(self) -> None:
        """Persist the TMDB ID cache to disk."""
        try:
            self._cache_dir.mkdir(parents=True, exist_ok=True)
            with open(self._cache_path, "w", encoding="utf-8") as f:
                json.dump(self._slug_cache, f, indent=2)
            logger.info("Saved %d TMDB ID cache entries to %s.", len(self._slug_cache), self._cache_path)
        except OSError as e:
            logger.warning("Failed to save TMDB ID cache: %s", e)

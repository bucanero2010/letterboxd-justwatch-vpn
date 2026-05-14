"""Hybrid Recommender module for the Hybrid Movie Recommender.

Orchestrates the full recommendation pipeline: interaction matrix construction
from MovieLens 25M + user watch history, LightFM model training with WARP loss
and item side features, scoring, ranking, and result serialization.
Manages model caching and staleness checks (7-day TTL).
"""

import hashlib
import io
import json
import logging
import os
import pickle
import time
import zipfile
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

import numpy as np
import requests
import scipy.sparse as sp

logger = logging.getLogger(__name__)

MOVIELENS_25M_URL = "https://files.grouplens.org/datasets/movielens/ml-25m.zip"
MODEL_TTL_DAYS = 7


@dataclass
class RecommendationResult:
    """A single movie recommendation with metadata and score."""

    tmdb_id: int
    title: str
    year: int
    score: float              # normalized 0.0–1.0
    poster_url: str | None
    runtime: int | None
    genres: list[str]


class HybridRecommender:
    """Orchestrates the hybrid recommendation pipeline.

    Handles interaction matrix construction from MovieLens 25M + user watch
    history, LightFM model training with WARP loss and item side features,
    scoring, ranking, and result serialization.
    """

    def __init__(self, config: dict, data_dir: Path):
        """Initialize with app config and data directory.

        Args:
            config: Application configuration dict containing at minimum
                'tmdb_key' for TMDB API access.
            data_dir: Path to the data directory for caching artifacts.
        """
        self.config = config
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Paths for cached artifacts
        self._model_path = self.data_dir / "lightfm_model.pkl"
        self._interaction_matrix_path = self.data_dir / "interaction_matrix.npz"
        self._ml_dir = self.data_dir / "ml-25m"
        self._ratings_path = self._ml_dir / "ratings.csv"
        self._links_path = self._ml_dir / "links.csv"

        # Internal state (populated during training)
        self._model = None
        self._tmdb_id_to_internal: dict[int, int] = {}
        self._internal_to_tmdb_id: dict[int, int] = {}
        self._interaction_matrix: Optional[sp.csr_matrix] = None
        self._user_index: Optional[int] = None
        self._watch_history_hash: Optional[str] = None

    def _download_movielens_25m(self, progress_callback=None) -> None:
        """Download and extract MovieLens 25M dataset if not already present.

        Downloads the ~250MB zip file from GroupLens and extracts it to
        the data directory. Only downloads if ratings.csv is not present.

        Args:
            progress_callback: Optional callable(message) for status updates.
        """
        if self._ratings_path.exists():
            logger.info("MovieLens 25M dataset already present at %s", self._ml_dir)
            return

        logger.info("Downloading MovieLens 25M dataset from GroupLens...")
        if progress_callback:
            progress_callback("Downloading MovieLens 25M dataset (~250MB)...")

        try:
            response = requests.get(MOVIELENS_25M_URL, stream=True, timeout=300)
            response.raise_for_status()

            # Read the entire zip into memory then extract
            zip_data = io.BytesIO()
            total_size = int(response.headers.get("content-length", 0))
            downloaded = 0

            for chunk in response.iter_content(chunk_size=8192):
                zip_data.write(chunk)
                downloaded += len(chunk)
                if progress_callback and total_size > 0:
                    pct = (downloaded / total_size) * 100
                    if downloaded % (8192 * 128) == 0:  # Update every ~1MB
                        progress_callback(
                            f"Downloading MovieLens 25M: {pct:.0f}%"
                        )

            if progress_callback:
                progress_callback("Extracting MovieLens 25M dataset...")

            zip_data.seek(0)
            with zipfile.ZipFile(zip_data) as zf:
                # Extract only the files we need
                needed_files = ["ml-25m/ratings.csv", "ml-25m/links.csv"]
                for member in zf.namelist():
                    if any(member.endswith(f.split("/")[-1]) and "ml-25m/" in member
                           for f in needed_files):
                        # Extract to data_dir, preserving the ml-25m/ subdirectory
                        zf.extract(member, self.data_dir)

            logger.info("MovieLens 25M dataset extracted to %s", self._ml_dir)

        except requests.RequestException as e:
            raise RuntimeError(
                f"Failed to download MovieLens 25M dataset: {e}. "
                f"Please download manually from {MOVIELENS_25M_URL} "
                f"and extract to {self._ml_dir}"
            ) from e
        except zipfile.BadZipFile as e:
            raise RuntimeError(
                f"Downloaded file is corrupt: {e}. Please try again."
            ) from e

    def _load_ratings_as_implicit(self, progress_callback=None) -> tuple[sp.csr_matrix, dict[int, int], dict[int, int]]:
        """Load MovieLens 25M ratings.csv and binarize to implicit feedback.

        Reads the ratings CSV, maps all ratings to 1 (implicit positive
        feedback), and constructs a sparse CSR interaction matrix.

        Args:
            progress_callback: Optional callable(message) for status updates.

        Returns:
            Tuple of (interaction_matrix, movielens_id_to_col, col_to_movielens_id):
                - interaction_matrix: CSR matrix of shape (n_users, n_items)
                  with all values = 1.0
                - movielens_id_to_col: dict mapping MovieLens movieId to column index
                - col_to_movielens_id: dict mapping column index to MovieLens movieId
        """
        import csv

        if progress_callback:
            progress_callback("Loading MovieLens 25M ratings...")

        logger.info("Loading ratings from %s", self._ratings_path)

        # First pass: collect unique user IDs and movie IDs
        user_ids: set[int] = set()
        movie_ids: set[int] = set()
        rows_data: list[tuple[int, int]] = []

        with open(self._ratings_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                user_id = int(row["userId"])
                movie_id = int(row["movieId"])
                user_ids.add(user_id)
                movie_ids.add(movie_id)
                rows_data.append((user_id, movie_id))

        # Build index mappings
        sorted_user_ids = sorted(user_ids)
        sorted_movie_ids = sorted(movie_ids)

        user_id_to_row = {uid: idx for idx, uid in enumerate(sorted_user_ids)}
        movielens_id_to_col = {mid: idx for idx, mid in enumerate(sorted_movie_ids)}
        col_to_movielens_id = {idx: mid for mid, idx in movielens_id_to_col.items()}

        n_users = len(sorted_user_ids)
        n_items = len(sorted_movie_ids)

        logger.info(
            "MovieLens 25M: %d users, %d items, %d interactions",
            n_users, n_items, len(rows_data),
        )

        if progress_callback:
            progress_callback(
                f"Building interaction matrix ({n_users} users × {n_items} items)..."
            )

        # Build sparse matrix with binarized values (all 1s)
        row_indices = np.array([user_id_to_row[uid] for uid, _ in rows_data], dtype=np.int32)
        col_indices = np.array([movielens_id_to_col[mid] for _, mid in rows_data], dtype=np.int32)
        data = np.ones(len(rows_data), dtype=np.float32)

        interaction_matrix = sp.csr_matrix(
            (data, (row_indices, col_indices)),
            shape=(n_users, n_items),
            dtype=np.float32,
        )

        return interaction_matrix, movielens_id_to_col, col_to_movielens_id

    def _build_index_mappings(self, movielens_id_to_col: dict[int, int], col_to_movielens_id: dict[int, int]) -> None:
        """Build TMDB ID ↔ internal column index mappings.

        Uses MovieLens links.csv to map between TMDB IDs and the internal
        0-indexed column positions in the interaction matrix.

        Args:
            movielens_id_to_col: Mapping from MovieLens movieId to column index.
            col_to_movielens_id: Mapping from column index to MovieLens movieId.
        """
        import csv

        self._tmdb_id_to_internal = {}
        self._internal_to_tmdb_id = {}

        if not self._links_path.exists():
            logger.warning("links.csv not found at %s, index mappings will be empty", self._links_path)
            return

        with open(self._links_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                movielens_id = int(row["movieId"])
                tmdb_id_str = row.get("tmdbId", "").strip()

                if tmdb_id_str and movielens_id in movielens_id_to_col:
                    tmdb_id = int(tmdb_id_str)
                    col_idx = movielens_id_to_col[movielens_id]
                    self._tmdb_id_to_internal[tmdb_id] = col_idx
                    self._internal_to_tmdb_id[col_idx] = tmdb_id

        logger.info(
            "Built index mappings: %d TMDB IDs mapped to internal indices",
            len(self._tmdb_id_to_internal),
        )

    def _insert_user_watch_history(
        self,
        interaction_matrix: sp.csr_matrix,
        watch_tmdb_ids: list[int],
        ratings: dict[int, float] = None,
    ) -> sp.csr_matrix:
        """Insert user watch history as a new row in the interaction matrix.

        Appends a new user row at the bottom of the interaction matrix with
        rating-based weights at each column corresponding to a watched film.
        If ratings are provided, uses normalized rating (rating/5.0) as weight.
        Otherwise uses 1.0 for all watched films.

        Args:
            interaction_matrix: Existing MovieLens interaction matrix.
            watch_tmdb_ids: List of TMDB IDs from the user's watch history.
            ratings: Optional dict mapping TMDB ID to rating (0.5-5.0 scale).

        Returns:
            New interaction matrix with the user row appended (shape: n_users+1, n_items).
        """
        n_items = interaction_matrix.shape[1]

        # Compute user's rating distribution for relative weighting
        rating_mean = 3.5  # default
        rating_std = 1.0   # default
        if ratings:
            rating_values = list(ratings.values())
            if rating_values:
                rating_mean = np.mean(rating_values)
                rating_std = np.std(rating_values) if len(rating_values) > 1 else 1.0
                logger.info(f"User rating distribution: mean={rating_mean:.2f}, std={rating_std:.2f}")

        # Find which watched films map to valid internal indices
        valid_cols = []
        valid_interactions = []
        for tmdb_id in watch_tmdb_ids:
            col_idx = self._tmdb_id_to_internal.get(tmdb_id)
            if col_idx is not None:
                # Use rating as weight if available
                if ratings and tmdb_id in ratings:
                    rating = ratings[tmdb_id]
                    # Z-score relative to user's rating distribution
                    # Positive = liked more than average, negative = liked less
                    z = (rating - rating_mean) / rating_std if rating_std > 0 else 0
                    interaction_val = z  # continuous value, not binary
                else:
                    interaction_val = 0.3  # Unknown rating = weak positive
                valid_cols.append(col_idx)
                valid_interactions.append(interaction_val)

        logger.info(
            "User watch history: %d films, %d mapped to interaction matrix columns",
            len(watch_tmdb_ids), len(valid_cols),
        )

        n_positive = sum(1 for v in valid_interactions if v > 0)
        n_negative = sum(1 for v in valid_interactions if v < 0)
        logger.info(f"  Positive interactions: {n_positive}, Negative: {n_negative}")

        # Build the user row as a sparse matrix (values are continuous z-scores)
        if valid_cols:
            row_indices = np.zeros(len(valid_cols), dtype=np.int32)
            col_indices = np.array(valid_cols, dtype=np.int32)
            data = np.array(valid_interactions, dtype=np.float32)
            user_row = sp.csr_matrix(
                (data, (row_indices, col_indices)),
                shape=(1, n_items),
                dtype=np.float32,
            )
        else:
            user_row = sp.csr_matrix((1, n_items), dtype=np.float32)

        # Stack the user row below the existing matrix
        combined = sp.vstack([interaction_matrix, user_row], format="csr")
        self._user_index = combined.shape[0] - 1

        return combined

    def _cache_interaction_matrix(self, matrix: sp.csr_matrix) -> None:
        """Cache the interaction matrix to disk as NPZ.

        Args:
            matrix: Sparse CSR interaction matrix to cache.
        """
        try:
            sp.save_npz(self._interaction_matrix_path, matrix)
            logger.info("Cached interaction matrix to %s", self._interaction_matrix_path)
        except OSError as e:
            logger.warning("Failed to cache interaction matrix: %s", e)

    def _compute_watch_history_hash(self, watch_history: list[dict]) -> str:
        """Compute a deterministic hash of the watch history for change detection.

        Args:
            watch_history: List of dicts with keys: title, year, slug.

        Returns:
            Hex digest string representing the watch history state.
        """
        # Sort by slug for deterministic ordering
        sorted_history = sorted(watch_history, key=lambda x: x.get("slug", ""))
        history_str = json.dumps(sorted_history, sort_keys=True)
        return hashlib.sha256(history_str.encode()).hexdigest()

    def is_model_fresh(self) -> bool:
        """Check if cached model exists and is less than 7 days old.

        Returns:
            True if a valid cached model exists and was created within the
            last 7 days, False otherwise.
        """
        if not self._model_path.exists():
            return False

        # Check file modification time
        mtime = self._model_path.stat().st_mtime
        age_days = (time.time() - mtime) / (60 * 60 * 24)

        if age_days >= MODEL_TTL_DAYS:
            logger.info("Cached model is %.1f days old (TTL: %d days), needs retraining", age_days, MODEL_TTL_DAYS)
            return False

        logger.info("Cached model is %.1f days old, still fresh", age_days)
        return True

    def _load_cached_model(self) -> bool:
        """Load a cached model from disk.

        Returns:
            True if model was loaded successfully, False otherwise.
        """
        if not self._model_path.exists():
            return False

        try:
            with open(self._model_path, "rb") as f:
                cached = pickle.load(f)

            self._model = cached["model"]
            self._tmdb_id_to_internal = cached["tmdb_id_to_internal"]
            self._internal_to_tmdb_id = cached["internal_to_tmdb_id"]
            self._watch_history_hash = cached.get("watch_history_hash")
            self._user_index = cached.get("user_index")

            logger.info("Loaded cached LightFM model from %s", self._model_path)
            return True

        except (pickle.UnpicklingError, KeyError, EOFError) as e:
            logger.warning("Corrupt model cache at %s: %s. Will retrain.", self._model_path, e)
            return False

    def _save_model(self, watch_history_hash: str) -> None:
        """Persist the trained model and index mappings to disk.

        Args:
            watch_history_hash: Hash of the watch history used for training.
        """
        payload = {
            "model": self._model,
            "tmdb_id_to_internal": self._tmdb_id_to_internal,
            "internal_to_tmdb_id": self._internal_to_tmdb_id,
            "watch_history_hash": watch_history_hash,
            "user_index": self._user_index,
        }

        try:
            with open(self._model_path, "wb") as f:
                pickle.dump(payload, f)
            logger.info("Saved trained LightFM model to %s", self._model_path)
        except OSError as e:
            logger.warning("Failed to save model: %s", e)

    def _incremental_update(self, watch_history: list[dict], current_hash: str, progress_callback=None) -> None:
        """Incrementally update the model with new watch history.

        Instead of full retraining, updates the user's interaction row and
        runs a few epochs of fit_partial to adjust the user vector.
        Much faster than full training (~seconds vs minutes).

        Args:
            watch_history: Updated watch history with ratings.
            current_hash: Hash of the new watch history.
            progress_callback: Optional progress callback.
        """
        from id_mapper import IDMapper

        if progress_callback:
            progress_callback("Resolving new watch history...")

        tmdb_token = self.config.get("tmdb_key", "")
        id_mapper = IDMapper(tmdb_token, self.data_dir)

        # Resolve watch history to TMDB IDs with ratings
        watch_tmdb_ids = []
        ratings_map = {}
        for film in watch_history:
            tmdb_id = id_mapper.resolve_slug_to_tmdb_id(
                slug=film.get("slug", ""),
                title=film.get("title", ""),
                year=film.get("year", 0),
            )
            if tmdb_id is not None:
                watch_tmdb_ids.append(tmdb_id)
                if film.get("rating") is not None:
                    ratings_map[tmdb_id] = film["rating"]
        id_mapper.save_cache()

        # Load the cached interaction matrix and update user row
        if self._interaction_matrix_path.exists():
            if progress_callback:
                progress_callback("Updating interaction matrix with new ratings...")
            base_matrix = sp.load_npz(self._interaction_matrix_path)
            # Remove the old user row (last row) and rebuild
            ml_matrix = base_matrix[:-1]
            self._interaction_matrix = self._insert_user_watch_history(
                ml_matrix, watch_tmdb_ids, ratings=ratings_map if ratings_map else None
            )

            # Load item features
            aligned_path = self.data_dir / "item_features_aligned.npz"
            item_features = None
            if aligned_path.exists():
                item_features = sp.load_npz(aligned_path)

            # Run 2 epochs of incremental training to adjust user vector
            if progress_callback:
                progress_callback("Incremental training (2 epochs)...")
            self._model.fit_partial(
                interactions=self._interaction_matrix,
                item_features=item_features,
                epochs=2,
                num_threads=os.cpu_count() or 2,
                verbose=False,
            )

            # Save updated model
            self._watch_history_hash = current_hash
            self._save_model(current_hash)
            sp.save_npz(self._interaction_matrix_path, self._interaction_matrix)

            if progress_callback:
                progress_callback("Incremental update complete!")
        else:
            # No cached matrix — fall through to full training
            logger.warning("No cached interaction matrix for incremental update. Will do full training.")
            self._model = None  # Force full retrain
            self.train(watch_history, progress_callback)

    def train(self, watch_history: list[dict], progress_callback=None) -> None:
        """Full training pipeline: resolve IDs → fetch metadata → engineer features → train LightFM.

        Orchestrates the complete recommendation model training:
        1. Check if cached model is fresh and watch history unchanged
        2. Download MovieLens 25M if not present
        3. Load ratings as implicit feedback (binarize all to 1)
        4. Build internal index mappings (TMDB ID ↔ column index)
        5. Resolve watch history slugs to TMDB IDs
        6. Insert user watch history into interaction matrix
        7. Fetch TMDB metadata for watched + candidate movies
        8. Build Item Feature Matrix (sparse TF-IDF + dense embeddings)
        9. Train LightFM with WARP loss, 64 components, 5 epochs
        10. Cache model and artifacts

        Args:
            watch_history: List of dicts with keys: title, year, slug.
            progress_callback: Optional callable(message) for status updates.
        """
        from lightfm import LightFM

        from feature_engineer import FeatureEngineer
        from id_mapper import IDMapper
        from tmdb_metadata import TMDBMetadataFetcher

        # Compute watch history hash for change detection
        current_hash = self._compute_watch_history_hash(watch_history)

        # Check if we can use cached model
        if self.is_model_fresh():
            if self._load_cached_model():
                if self._watch_history_hash == current_hash:
                    logger.info("Cached model is fresh and watch history unchanged. Skipping training.")
                    if progress_callback:
                        progress_callback("Using cached model (still fresh)")
                    return
                else:
                    # Watch history changed but model structure is same — do incremental update
                    logger.info("Watch history changed. Doing incremental update...")
                    if progress_callback:
                        progress_callback("Watch history changed — incremental update...")
                    self._incremental_update(watch_history, current_hash, progress_callback)
                    return

        if progress_callback:
            progress_callback("No cached model found. Running full training pipeline...")

        # Step 1: Download MovieLens 25M if needed
        self._download_movielens_25m(progress_callback)

        # Step 2: Load ratings as implicit feedback
        if progress_callback:
            progress_callback("Loading MovieLens 25M ratings...")
        ml_matrix, movielens_id_to_col, col_to_movielens_id = self._load_ratings_as_implicit(progress_callback)

        # Subsample to top 5K most active users for faster training
        if progress_callback:
            progress_callback("Subsampling to most active users...")
        max_users = 5000
        if ml_matrix.shape[0] > max_users:
            user_activity = np.array(ml_matrix.sum(axis=1)).flatten()
            top_indices = np.argsort(-user_activity)[:max_users]
            ml_matrix = ml_matrix[top_indices]
            logger.info(
                "Subsampled to %d most active users (%d interactions)",
                ml_matrix.shape[0], ml_matrix.nnz,
            )

        # Step 3: Build index mappings
        if progress_callback:
            progress_callback("Building ID mappings...")
        self._build_index_mappings(movielens_id_to_col, col_to_movielens_id)

        # Step 4: Resolve watch history to TMDB IDs
        if progress_callback:
            progress_callback("Resolving watch history to TMDB IDs...")

        tmdb_token = self.config.get("tmdb_key", "")
        id_mapper = IDMapper(tmdb_token, self.data_dir)

        watch_tmdb_ids = []
        ratings_map = {}  # tmdb_id -> rating (0.5-5.0)
        unmapped_films = []  # films that couldn't be included in training
        for film in watch_history:
            tmdb_id = id_mapper.resolve_slug_to_tmdb_id(
                slug=film.get("slug", ""),
                title=film.get("title", ""),
                year=film.get("year", 0),
            )
            if tmdb_id is not None:
                # Check if this TMDB ID maps to a MovieLens ID
                if tmdb_id in self._tmdb_id_to_internal:
                    watch_tmdb_ids.append(tmdb_id)
                    if film.get("rating") is not None:
                        ratings_map[tmdb_id] = film["rating"]
                else:
                    unmapped_films.append(f"{film.get('title', '?')} ({film.get('year', '?')})")
            else:
                unmapped_films.append(f"{film.get('title', '?')} ({film.get('year', '?')}) [no TMDB match]")

        id_mapper.save_cache()

        logger.info(
            "Resolved %d/%d watch history films to training IDs (%d with ratings, %d excluded)",
            len(watch_tmdb_ids), len(watch_history), len(ratings_map), len(unmapped_films),
        )

        # Save unmapped films list for UI display
        if unmapped_films:
            import json as _json
            unmapped_path = self.data_dir / "unmapped_films.json"
            with open(unmapped_path, "w") as f:
                _json.dump(unmapped_films, f, indent=2)
            if progress_callback:
                progress_callback(f"⚠️ {len(unmapped_films)} films excluded (not in MovieLens dataset)")

        # Step 5: Insert user watch history into interaction matrix
        if progress_callback:
            progress_callback("Building interaction matrix with user history...")
        self._interaction_matrix = self._insert_user_watch_history(
            ml_matrix, watch_tmdb_ids, ratings=ratings_map if ratings_map else None
        )
        self._cache_interaction_matrix(self._interaction_matrix)

        # Step 6: Fetch TMDB metadata for feature engineering
        if progress_callback:
            progress_callback("Fetching TMDB metadata...")

        metadata_fetcher = TMDBMetadataFetcher(
            api_token=tmdb_token,
            cache_path=self.data_dir / "tmdb_metadata_cache.json",
        )

        # Fetch metadata for all movies that have internal indices
        all_tmdb_ids = list(self._tmdb_id_to_internal.keys())
        metadata = metadata_fetcher.fetch_batch(
            all_tmdb_ids,
            progress_callback=lambda cur, tot: (
                progress_callback(f"Fetching metadata: {cur}/{tot} ({cur*100//tot}%)")
                if progress_callback and (cur % 10000 == 0 or cur == tot) else None
            ),
        )
        metadata_fetcher.save_cache()

        # Step 7: Build Item Feature Matrix
        if progress_callback:
            progress_callback("Engineering features (TF-IDF + embeddings)...")

        feature_engineer = FeatureEngineer(cache_dir=self.data_dir, min_feature_count=20)

        # Only build features for movies that have metadata AND are in our index
        feature_metadata = {
            tmdb_id: meta
            for tmdb_id, meta in metadata.items()
            if tmdb_id in self._tmdb_id_to_internal
        }

        if len(feature_metadata) < 10:
            logger.warning(
                "Only %d movies have both metadata and index mappings. "
                "Recommendations may be limited.",
                len(feature_metadata),
            )

        item_feature_matrix, tmdb_id_order = feature_engineer.build_item_feature_matrix(feature_metadata, use_embeddings=False)

        # Build the LightFM-compatible item features matrix
        # Using side features only (no identity matrix) for fast training.
        # The collaborative signal still flows through the interaction matrix.
        n_items = self._interaction_matrix.shape[1]
        n_side_features = item_feature_matrix.shape[1]

        # Build side features aligned to item indices (zeros for items without metadata)
        item_features_aligned = sp.lil_matrix((n_items, n_side_features), dtype=np.float32)

        for row_idx, tmdb_id in enumerate(tmdb_id_order):
            col_idx = self._tmdb_id_to_internal.get(tmdb_id)
            if col_idx is not None and col_idx < n_items:
                item_features_aligned[col_idx] = item_feature_matrix[row_idx]

        item_features_aligned = item_features_aligned.tocsr()

        logger.info(
            "Item features matrix: %d items × %d side features (no identity)",
            item_features_aligned.shape[0], item_features_aligned.shape[1],
        )

        # Cache the aligned features for scoring
        try:
            sp.save_npz(self.data_dir / "item_features_aligned.npz", item_features_aligned)
        except OSError as e:
            logger.warning("Failed to cache aligned item features: %s", e)

        # Step 8: Train LightFM model
        if progress_callback:
            progress_callback("Training LightFM model (WARP loss, 64 components, 5 epochs)...")

        self._model = LightFM(
            loss="warp",
            no_components=64,
            learning_rate=0.05,
            random_state=42,
        )

        logger.info(
            "Training LightFM: %d users × %d items, %d item features",
            self._interaction_matrix.shape[0],
            self._interaction_matrix.shape[1],
            item_features_aligned.shape[1],
        )

        # Train epoch-by-epoch for progress reporting
        n_epochs = 5
        for epoch in range(n_epochs):
            if progress_callback:
                progress_callback(f"Training LightFM (epoch {epoch + 1}/{n_epochs})...")
            self._model.fit_partial(
                interactions=self._interaction_matrix,
                item_features=item_features_aligned,
                epochs=1,
                num_threads=os.cpu_count() or 2,
                verbose=False,
            )

        logger.info("LightFM training complete.")

        # Step 9: Save model and artifacts
        self._watch_history_hash = current_hash
        self._save_model(current_hash)

        if progress_callback:
            progress_callback("Training complete! Model saved.")

    def retrain(self, watch_history: list[dict], progress_callback=None) -> None:
        """Force retrain regardless of cache freshness.

        Deletes the cached model and runs the full training pipeline.

        Args:
            watch_history: List of dicts with keys: title, year, slug.
            progress_callback: Optional callable(message) for status updates.
        """
        # Remove cached model to force retraining
        if self._model_path.exists():
            try:
                self._model_path.unlink()
                logger.info("Removed cached model for forced retraining.")
            except OSError as e:
                logger.warning("Failed to remove cached model: %s", e)

        # Reset internal state
        self._model = None
        self._watch_history_hash = None

        # Run full training pipeline
        self.train(watch_history, progress_callback)

    def recommend(self, n: int = 50) -> list[RecommendationResult]:
        """Score candidates and return top-N ranked recommendations.

        Predicts scores for all candidate movies (excluding watch history),
        applies min-max normalization to [0.0, 1.0], ranks by descending
        score, and returns top-N RecommendationResult objects populated
        with metadata from the TMDB cache.

        Args:
            n: Number of recommendations to return (default 50).

        Returns:
            List of RecommendationResult objects sorted by descending score.

        Raises:
            RuntimeError: If the model has not been trained yet.
        """
        if self._model is None:
            raise RuntimeError(
                "Model has not been trained. Call train() before recommend()."
            )
        if self._user_index is None:
            raise RuntimeError(
                "User index not set. Call train() before recommend()."
            )

        # Build candidate pool: all internal item indices NOT in user's watch history
        n_items = len(self._internal_to_tmdb_id)
        watched_internal_ids = set()
        for tmdb_id, internal_id in self._tmdb_id_to_internal.items():
            # Check if this item was watched by looking at the interaction matrix
            if (self._interaction_matrix is not None
                    and internal_id < self._interaction_matrix.shape[1]
                    and self._interaction_matrix[self._user_index, internal_id] > 0):
                watched_internal_ids.add(internal_id)

        # Construct candidate item IDs (exclude watched)
        candidate_ids = np.array(
            [idx for idx in range(n_items) if idx not in watched_internal_ids],
            dtype=np.int32,
        )

        if len(candidate_ids) < 1000:
            logger.warning(
                "Candidate pool contains only %d movies after filtering "
                "(target: 5,000+). Limited candidate coverage.",
                len(candidate_ids),
            )

        logger.info(
            "Scoring %d candidate movies (excluded %d watched)",
            len(candidate_ids),
            len(watched_internal_ids),
        )

        if len(candidate_ids) == 0:
            logger.warning("No candidate movies available for recommendation.")
            return []

        # Load item features if available (for scoring with side features)
        # Must match the format used during training: identity + side features
        item_features = None
        item_features_path = self.data_dir / "item_features.npz"
        if item_features_path.exists():
            try:
                side_features_raw = sp.load_npz(item_features_path)
                n_items = len(self._internal_to_tmdb_id)
                # Reconstruct aligned side features
                n_side = side_features_raw.shape[1]
                side_aligned = sp.lil_matrix((n_items, n_side), dtype=np.float32)
                # The cached matrix rows correspond to sorted tmdb_ids that had metadata
                # For scoring, we just need identity + zeros for items without features
                # since the model was trained with this structure
                identity = sp.eye(n_items, dtype=np.float32, format="csr")
                # Load the full aligned features if we saved them during training
                aligned_path = self.data_dir / "item_features_aligned.npz"
                if aligned_path.exists():
                    item_features = sp.load_npz(aligned_path)
                else:
                    # Fallback: use identity only (no side features for scoring)
                    item_features = identity
                logger.info("Loaded item features for scoring: %s", item_features.shape)
            except Exception as e:
                logger.warning("Failed to load item features, scoring without them: %s", e)

        # Predict scores for all candidates
        user_ids = np.full(len(candidate_ids), self._user_index, dtype=np.int32)
        raw_scores = self._model.predict(
            user_ids=user_ids,
            item_ids=candidate_ids,
            item_features=item_features,
        )

        # Apply min-max normalization to [0.0, 1.0]
        score_min = raw_scores.min()
        score_max = raw_scores.max()

        if score_max - score_min > 0:
            normalized_scores = (raw_scores - score_min) / (score_max - score_min)
        else:
            # All scores are identical — assign uniform 0.5
            normalized_scores = np.full_like(raw_scores, 0.5)

        # Rank by descending normalized score
        top_indices = np.argsort(-normalized_scores)[:n]

        # Load TMDB metadata cache for populating result fields
        tmdb_cache = self._load_tmdb_metadata_cache()

        # Build RecommendationResult objects
        results = []
        for idx in top_indices:
            internal_id = candidate_ids[idx]
            score = float(normalized_scores[idx])
            tmdb_id = self._internal_to_tmdb_id.get(internal_id)

            if tmdb_id is None:
                continue

            # Look up metadata from TMDB cache
            meta = tmdb_cache.get(tmdb_id)
            if meta:
                title = meta.get("title", f"Movie {tmdb_id}")
                year = meta.get("year", 0)
                poster_path = meta.get("poster_path")
                poster_url = (
                    f"https://image.tmdb.org/t/p/w500{poster_path}"
                    if poster_path
                    else None
                )
                runtime = meta.get("runtime")
                genres = meta.get("genres", [])
            else:
                title = f"Movie {tmdb_id}"
                year = 0
                poster_url = None
                runtime = None
                genres = []

            results.append(
                RecommendationResult(
                    tmdb_id=tmdb_id,
                    title=title,
                    year=year,
                    score=score,
                    poster_url=poster_url,
                    runtime=runtime,
                    genres=genres,
                )
            )

        logger.info(
            "Generated %d recommendations (requested %d)", len(results), n
        )
        return results

    def _load_tmdb_metadata_cache(self) -> dict[int, dict]:
        """Load the TMDB metadata cache from disk for result population.

        Returns:
            Dictionary mapping tmdb_id (int) to metadata dict fields.
        """
        cache_path = self.data_dir / "tmdb_metadata_cache.json"
        if not cache_path.exists():
            logger.warning("TMDB metadata cache not found at %s", cache_path)
            return {}

        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            return {int(k): v for k, v in raw.items()}
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning("Failed to load TMDB metadata cache: %s", e)
            return {}

    def serialize_results(self, results: list[RecommendationResult], path: Path) -> None:
        """Serialize recommendation results to JSON.

        Args:
            results: List of RecommendationResult objects to serialize.
            path: Path to write the JSON file.
        """
        serialized = [asdict(r) for r in results]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(serialized, f, ensure_ascii=False, indent=2)

    def deserialize_results(self, path: Path) -> list[RecommendationResult]:
        """Deserialize recommendation results from JSON.

        Args:
            path: Path to the JSON file to read.

        Returns:
            List of RecommendationResult objects.
        """
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return [
            RecommendationResult(
                tmdb_id=item["tmdb_id"],
                title=item["title"],
                year=item["year"],
                score=item["score"],
                poster_url=item.get("poster_url"),
                runtime=item.get("runtime"),
                genres=item.get("genres", []),
            )
            for item in data
        ]

    def serialize_feature_matrix_metadata(self, path: Path) -> None:
        """Serialize Item Feature Matrix metadata to JSON for inspection.

        Saves dimensions, sparsity statistics, min_df threshold, a sample
        of feature names, and creation timestamp.

        Args:
            path: Path to write the metadata JSON file.
        """
        from datetime import datetime, timezone

        item_features_path = self.data_dir / "item_features.npz"
        if not item_features_path.exists():
            logger.warning(
                "Item feature matrix not found at %s, cannot serialize metadata.",
                item_features_path,
            )
            return

        try:
            item_features = sp.load_npz(item_features_path)
        except Exception as e:
            logger.warning("Failed to load item feature matrix: %s", e)
            return

        n_items, total_features = item_features.shape
        n_dense_features = 384  # sentence-transformer embedding dimension
        n_sparse_features = total_features - n_dense_features

        # Compute sparsity: fraction of zero entries
        n_nonzero = item_features.nnz
        total_entries = n_items * total_features
        sparsity = round(1.0 - (n_nonzero / total_entries), 4) if total_entries > 0 else 0.0

        # Try to load feature names from the TF-IDF vectorizer output
        # We sample up to 10 feature names from the sparse block
        feature_names_sample = self._get_feature_names_sample(n_sparse_features)

        metadata = {
            "n_items": n_items,
            "n_sparse_features": n_sparse_features,
            "n_dense_features": n_dense_features,
            "total_features": total_features,
            "sparsity": sparsity,
            "min_df_threshold": 3,
            "feature_names_sample": feature_names_sample,
            "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }

        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
            logger.info("Saved feature matrix metadata to %s", path)
        except OSError as e:
            logger.warning("Failed to save feature matrix metadata: %s", e)

    def _get_feature_names_sample(self, n_sparse_features: int) -> list[str]:
        """Get a sample of feature names from cached feature artifacts.

        Attempts to reconstruct feature names from the TF-IDF vectorizer
        by re-reading the TMDB metadata cache and building feature tokens.

        Args:
            n_sparse_features: Number of sparse features in the matrix.

        Returns:
            List of up to 10 sample feature name strings.
        """
        # Try to load from a cached feature names file if available
        feature_names_path = self.data_dir / "feature_names.json"
        if feature_names_path.exists():
            try:
                with open(feature_names_path, "r", encoding="utf-8") as f:
                    all_names = json.load(f)
                return all_names[:10]
            except (json.JSONDecodeError, ValueError):
                pass

        # Fallback: return generic placeholder names
        sample = []
        generic_prefixes = ["genre:", "director:", "cast:", "keyword:"]
        for i, prefix in enumerate(generic_prefixes):
            if i < n_sparse_features:
                sample.append(f"{prefix}(feature_{i})")
        return sample[:10]

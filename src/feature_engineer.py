"""Feature Engineer module for the Hybrid Movie Recommender.

Builds the Item Feature Matrix: sparse TF-IDF vectors from categorical metadata
(genres, directors, cast, keywords) concatenated with dense 384-dimensional
sentence-transformer plot embeddings. Handles feature pruning, concatenation,
and caching of all feature artifacts.
"""

import logging
from pathlib import Path

import numpy as np
import scipy.sparse as sp
from sklearn.feature_extraction.text import TfidfVectorizer

from tmdb_metadata import MovieMetadata

logger = logging.getLogger(__name__)


class FeatureEngineer:
    """Builds sparse and dense feature matrices for the hybrid recommender.

    Constructs TF-IDF weighted sparse features from categorical metadata
    (genres, directors, cast, keywords) and dense sentence-transformer
    embeddings from plot overviews.
    """

    def __init__(self, cache_dir: Path, min_feature_count: int = 3):
        """Initialize with cache directory and feature pruning threshold.

        Args:
            cache_dir: Directory for caching feature artifacts.
            min_feature_count: Minimum number of movies a feature must appear in
                to be retained. Features appearing in fewer movies are pruned.
        """
        self.cache_dir = Path(cache_dir)
        self.min_feature_count = min_feature_count

    def _build_feature_tokens(self, metadata: MovieMetadata) -> list[str]:
        """Build a list of feature tokens from a movie's categorical metadata.

        Each categorical feature is prefixed with its type to create distinct
        feature tokens: genre:X, director:X, cast:X, keyword:X.

        Args:
            metadata: MovieMetadata object for a single movie.

        Returns:
            A list of prefixed feature token strings.
        """
        tokens = []

        for genre in metadata.genres:
            tokens.append(f"genre:{genre}")

        for director in metadata.directors:
            tokens.append(f"director:{director}")

        for actor in metadata.cast:
            tokens.append(f"cast:{actor}")

        for keyword in metadata.keywords:
            tokens.append(f"keyword:{keyword}")

        return tokens

    def build_sparse_features(
        self, metadata: dict[int, MovieMetadata]
    ) -> tuple[sp.csr_matrix, list[str]]:
        """Build TF-IDF weighted sparse feature matrix from categorical metadata.

        Constructs feature documents from each movie's genres, directors, cast,
        and keywords, then applies TF-IDF weighting with sublinear term frequency.
        Features appearing in fewer than `min_feature_count` movies are pruned.

        Args:
            metadata: Dictionary mapping tmdb_id to MovieMetadata objects.

        Returns:
            Tuple of (sparse_matrix, feature_names) where:
                - sparse_matrix: CSR matrix of shape (n_movies, n_features)
                  with TF-IDF weights
                - feature_names: List of feature name strings corresponding
                  to matrix columns
        """
        # Build ordered list of tmdb_ids and their feature token lists
        tmdb_ids = sorted(metadata.keys())
        token_lists = [
            self._build_feature_tokens(metadata[tmdb_id]) for tmdb_id in tmdb_ids
        ]

        # Use a custom analyzer that returns pre-tokenized lists directly.
        # This avoids issues with multi-word feature names (e.g., "director:Denis Villeneuve")
        # being split by whitespace tokenization.
        vectorizer = TfidfVectorizer(
            sublinear_tf=True,
            min_df=self.min_feature_count,
            analyzer=lambda tokens: tokens,
            lowercase=False,
        )

        tfidf_matrix = vectorizer.fit_transform(token_lists)
        feature_names = vectorizer.get_feature_names_out().tolist()

        logger.info(
            f"Built sparse TF-IDF matrix: {tfidf_matrix.shape[0]} movies × "
            f"{tfidf_matrix.shape[1]} features "
            f"(pruned features appearing in < {self.min_feature_count} movies)"
        )

        # Cache feature names for metadata serialization
        self._save_feature_names(feature_names)

        return tfidf_matrix, feature_names

    def _save_feature_names(self, feature_names: list[str]) -> None:
        """Save feature names to JSON for metadata inspection.

        Args:
            feature_names: List of feature name strings.
        """
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        feature_names_path = self.cache_dir / "feature_names.json"
        try:
            import json
            with open(feature_names_path, "w", encoding="utf-8") as f:
                json.dump(feature_names, f, ensure_ascii=False)
            logger.info(f"Cached feature names to {feature_names_path}")
        except OSError as e:
            logger.warning(f"Failed to cache feature names: {e}")

    def build_dense_embeddings(
        self, metadata: dict[int, MovieMetadata]
    ) -> np.ndarray:
        """Generate 384-dim sentence-transformer embeddings for plot overviews.

        Loads cached embeddings if available. Otherwise loads the all-MiniLM-L6-v2
        model and encodes each movie's plot overview text. Movies with empty or
        missing plot overviews receive a zero vector.

        Args:
            metadata: Dictionary mapping tmdb_id to MovieMetadata objects.

        Returns:
            NumPy array of shape (n_movies, 384) with dtype float32.
            Row order matches sorted tmdb_ids.
        """
        tmdb_ids = sorted(metadata.keys())
        n_movies = len(tmdb_ids)
        embedding_dim = 384

        # Try loading cached embeddings first
        cache_path = self.cache_dir / "plot_embeddings.npz"
        if cache_path.exists():
            try:
                cached = np.load(cache_path)
                cached_emb = cached["embeddings"]
                if cached_emb.shape[0] == n_movies and cached_emb.shape[1] == embedding_dim:
                    logger.info(f"Loaded cached embeddings: {cached_emb.shape}")
                    return cached_emb
                else:
                    logger.info(f"Cached embeddings shape mismatch ({cached_emb.shape} vs expected ({n_movies}, {embedding_dim})), recomputing...")
            except Exception as e:
                logger.warning(f"Failed to load cached embeddings: {e}")

        from sentence_transformers import SentenceTransformer

        # Separate movies with and without plot overviews
        texts_to_encode = []
        indices_with_text = []

        for i, tmdb_id in enumerate(tmdb_ids):
            overview = metadata[tmdb_id].overview
            if overview and overview.strip():
                texts_to_encode.append(overview)
                indices_with_text.append(i)

        # Initialize embeddings as zeros (handles missing plots by default)
        embeddings = np.zeros((n_movies, embedding_dim), dtype=np.float32)

        if texts_to_encode:
            logger.info(
                f"Encoding {len(texts_to_encode)} plot overviews "
                f"({n_movies - len(texts_to_encode)} movies have empty plots)"
            )
            model = SentenceTransformer("all-MiniLM-L6-v2", device="cpu")
            encoded = model.encode(
                texts_to_encode,
                show_progress_bar=False,
                convert_to_numpy=True,
                normalize_embeddings=False,
            )
            # Place encoded embeddings at the correct row indices
            for idx, embedding in zip(indices_with_text, encoded):
                embeddings[idx] = embedding
        else:
            logger.info("No plot overviews to encode, using zero vectors for all movies")

        # Cache embeddings to disk
        self._save_embeddings_cache(embeddings)

        logger.info(
            f"Built dense embeddings: {embeddings.shape[0]} movies × "
            f"{embeddings.shape[1]} dimensions"
        )

        return embeddings

    def _save_embeddings_cache(self, embeddings: np.ndarray) -> None:
        """Save embeddings array to NPZ cache file.

        Args:
            embeddings: NumPy array of shape (n_movies, 384).
        """
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        cache_path = self.cache_dir / "plot_embeddings.npz"
        try:
            np.savez_compressed(cache_path, embeddings=embeddings)
            logger.info(f"Cached plot embeddings to {cache_path}")
        except OSError as e:
            logger.warning(f"Failed to cache plot embeddings: {e}")

    def build_item_feature_matrix(
        self, metadata: dict[int, MovieMetadata], use_embeddings: bool = True
    ) -> tuple[sp.csr_matrix, list[int]]:
        """Build the combined Item Feature Matrix.

        If use_embeddings=True, concatenates sparse TF-IDF with PCA-reduced
        plot embeddings. If False, uses only sparse TF-IDF features (faster,
        avoids PyTorch segfaults on some platforms).
        the sparse TF-IDF matrix with the dense embeddings (converted to sparse CSR)
        using scipy.sparse.hstack.

        Args:
            metadata: Dictionary mapping tmdb_id to MovieMetadata objects.

        Returns:
            Tuple of (item_feature_matrix, tmdb_id_order) where:
                - item_feature_matrix: CSR matrix of shape (n_movies, K + 384)
                  where K is the number of sparse TF-IDF features
                - tmdb_id_order: Sorted list of tmdb_ids corresponding to matrix rows
        """
        # Build sparse TF-IDF features
        sparse_matrix, feature_names = self.build_sparse_features(metadata)

        tmdb_id_order = sorted(metadata.keys())

        if use_embeddings:
            try:
                # Build dense embeddings
                embeddings = self.build_dense_embeddings(metadata)

                # Reduce embeddings from 384 dims to 30 via PCA for sparsity
                from sklearn.decomposition import PCA

                n_pca_components = 30
                logger.info(f"Reducing embeddings from {embeddings.shape[1]} to {n_pca_components} dims via PCA")
                pca = PCA(n_components=n_pca_components, random_state=42)
                embeddings_reduced = pca.fit_transform(embeddings).astype(np.float32)
                logger.info(f"PCA explained variance: {pca.explained_variance_ratio_.sum():.2%}")

                # Convert reduced embeddings to sparse CSR for hstack
                sparse_embeddings = sp.csr_matrix(embeddings_reduced)

                # Concatenate sparse TF-IDF with reduced embeddings
                item_feature_matrix = sp.hstack(
                    [sparse_matrix, sparse_embeddings], format="csr"
                )

                logger.info(
                    f"Built item feature matrix: {item_feature_matrix.shape[0]} movies × "
                    f"{item_feature_matrix.shape[1]} features "
                    f"({sparse_matrix.shape[1]} sparse + {n_pca_components} PCA dims)"
                )
            except Exception as e:
                logger.warning(f"Embeddings failed ({e}), using sparse features only")
                item_feature_matrix = sparse_matrix
        else:
            item_feature_matrix = sparse_matrix
            logger.info(
                f"Built item feature matrix (sparse only): {item_feature_matrix.shape[0]} movies × "
                f"{item_feature_matrix.shape[1]} features"
            )

        # Cache the combined matrix
        self._save_item_features_cache(item_feature_matrix)

        return item_feature_matrix, tmdb_id_order

    def _save_item_features_cache(self, matrix: sp.csr_matrix) -> None:
        """Save item feature matrix to NPZ cache file.

        Args:
            matrix: Sparse CSR matrix to cache.
        """
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        cache_path = self.cache_dir / "item_features.npz"
        try:
            sp.save_npz(cache_path, matrix)
            logger.info(f"Cached item feature matrix to {cache_path}")
        except OSError as e:
            logger.warning(f"Failed to cache item feature matrix: {e}")

    def save_cache(self) -> None:
        """Persist all feature artifacts (embeddings and feature matrix) to disk.

        This is a convenience method that ensures the cache directory exists.
        Individual caching is handled by build_dense_embeddings and
        build_item_feature_matrix during their execution. This method can be
        called to verify cache directory readiness.
        """
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Feature cache directory ready: {self.cache_dir}")

# Implementation Plan: Hybrid Movie Recommender

## Overview

This plan implements a hybrid movie recommendation engine using LightFM that integrates into the existing Letterboxd watchlist Streamlit app. The implementation proceeds module-by-module: ID mapping, TMDB metadata fetching, feature engineering (sparse TF-IDF + dense embeddings), LightFM model training/scoring, and finally the Streamlit UI tab. Each module is built incrementally with property-based tests validating correctness properties from the design.

## Tasks

- [x] 1. Install dependencies and set up project structure
  - Add `lightfm>=1.17`, `sentence-transformers>=2.2.0`, `scipy>=1.11.0`, `scikit-learn>=1.3.0`, `numpy>=1.24.0`, `hypothesis>=6.0`, `pytest>=7.0`, `pytest-mock>=3.0` to `requirements.txt`
  - Create empty module files: `src/id_mapper.py`, `src/tmdb_metadata.py`, `src/feature_engineer.py`, `src/recommender.py`
  - Create test directory `tests/` with `__init__.py` and empty test files: `tests/test_id_mapper.py`, `tests/test_tmdb_metadata.py`, `tests/test_feature_engineer.py`, `tests/test_recommender.py`
  - _Requirements: 1.1, 2.1, 3.1, 4.1, 5.1_

- [x] 2. Implement ID Mapper module
  - [x] 2.1 Implement `IDMapper` class in `src/id_mapper.py`
    - Implement `__init__` to load MovieLens `links.csv` (TMDB ID ↔ MovieLens ID mapping) and TMDB ID cache from `data/tmdb_id_cache.json`
    - Implement `resolve_slug_to_tmdb_id(slug, title, year)` using TMDB search API with caching
    - Implement `tmdb_id_to_movielens_id(tmdb_id)` and `movielens_id_to_tmdb_id(movielens_id)` bidirectional lookups
    - Implement `save_cache()` to persist the TMDB ID cache to JSON
    - Handle missing/unresolvable films by logging a warning and returning `None`
    - _Requirements: 1.2, 1.3, 1.4, 8.1, 8.2, 8.3, 8.4_

  - [ ]* 2.2 Write property test for TMDB ID Cache Round-Trip
    - **Property 1: TMDB ID Cache Round-Trip**
    - **Validates: Requirements 1.4**

  - [ ]* 2.3 Write property test for ID Mapping Round-Trip
    - **Property 13: ID Mapping Round-Trip**
    - **Validates: Requirements 8.5**

  - [ ]* 2.4 Write unit tests for ID Mapper edge cases
    - Test unresolvable film returns `None` and logs warning (Req 1.3)
    - Test `links.csv` loading produces non-empty mapping (Req 8.1)
    - Test unknown TMDB ID returns `None` from `tmdb_id_to_movielens_id` (Req 8.4)
    - _Requirements: 1.3, 8.1, 8.4_

- [x] 3. Implement TMDB Metadata Fetcher module
  - [x] 3.1 Implement `MovieMetadata` dataclass and `TMDBMetadataFetcher` class in `src/tmdb_metadata.py`
    - Define `MovieMetadata` dataclass with fields: tmdb_id, title, year, genres, directors, cast (top 5), keywords, overview, poster_path, runtime
    - Implement `__init__` to load metadata cache from `data/tmdb_metadata_cache.json`
    - Implement `fetch_movie(tmdb_id)` with TMDB API calls for movie details, credits, and keywords endpoints
    - Implement `fetch_batch(tmdb_ids, progress_callback)` with rate-limit handling (exponential backoff, max 3 retries)
    - Implement `fetch_candidates(genre_ids, min_pages)` using TMDB discover endpoints (popular, top-rated, genre-based) targeting 5,000+ candidates
    - Implement `save_cache()` to persist metadata cache to JSON
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 7.1, 7.2_

  - [ ]* 3.2 Write property test for TMDB Metadata Cache Round-Trip
    - **Property 3: TMDB Metadata Cache Round-Trip**
    - **Validates: Requirements 2.2**

  - [ ]* 3.3 Write unit tests for TMDB Metadata Fetcher
    - Test retry on HTTP 429 with exponential backoff (Req 2.3)
    - Test candidate pool warning when < 1,000 movies (Req 7.5)
    - _Requirements: 2.3, 7.5_

- [x] 4. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Implement Feature Engineer module — Sparse Features
  - [x] 5.1 Implement sparse TF-IDF feature construction in `src/feature_engineer.py`
    - Implement `FeatureEngineer.__init__` with cache directory and `min_feature_count=3` threshold
    - Implement `build_sparse_features(metadata)` using scikit-learn `TfidfVectorizer` with `sublinear_tf=True`, `min_df=3`
    - Construct feature documents from categorical metadata: `genre:X`, `director:X`, `cast:X`, `keyword:X`
    - Prune features appearing in fewer than 3 movies
    - Return sparse CSR matrix and feature name list
    - _Requirements: 3.1, 3.2, 3.3_

  - [ ]* 5.2 Write property test for Sparse TF-IDF Feature Construction Invariants
    - **Property 4: Sparse TF-IDF Feature Construction Invariants**
    - **Validates: Requirements 3.1, 3.2, 3.3**

  - [ ]* 5.3 Write property test for Feature Label Reconstruction
    - **Property 5: Feature Label Reconstruction**
    - **Validates: Requirements 3.4**

- [x] 6. Implement Feature Engineer module — Dense Embeddings
  - [x] 6.1 Implement dense embedding generation in `src/feature_engineer.py`
    - Implement `build_dense_embeddings(metadata)` using `sentence-transformers` model `all-MiniLM-L6-v2`
    - Generate 384-dimensional embedding vectors for each movie's plot overview
    - Use zero vector for movies with empty/missing plot overview
    - Cache embeddings to `data/plot_embeddings.npz`
    - _Requirements: 4.1, 4.2, 4.3_

  - [x] 6.2 Implement Item Feature Matrix concatenation
    - Implement `build_item_feature_matrix(metadata)` that calls `build_sparse_features` and `build_dense_embeddings`
    - Concatenate sparse TF-IDF matrix with dense embeddings (converted to sparse CSR) using `scipy.sparse.hstack`
    - Cache combined matrix to `data/item_features.npz`
    - Implement `save_cache()` for all feature artifacts
    - _Requirements: 4.4_

  - [ ]* 6.3 Write property test for Embedding Dimensionality and Zero-Vector Invariant
    - **Property 6: Embedding Dimensionality and Zero-Vector Invariant**
    - **Validates: Requirements 4.1, 4.2**

  - [ ]* 6.4 Write property test for Embedding Cache Round-Trip
    - **Property 7: Embedding Cache Round-Trip**
    - **Validates: Requirements 4.3**

  - [ ]* 6.5 Write property test for Item Feature Matrix Concatenation Shape
    - **Property 8: Item Feature Matrix Concatenation Shape**
    - **Validates: Requirements 4.4**

  - [ ]* 6.6 Write property test for Feature Matrix Metadata Serialization Round-Trip
    - **Property 15: Feature Matrix Metadata Serialization Round-Trip**
    - **Validates: Requirements 11.4**

- [x] 7. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. Implement Recommender module — Interaction Matrix and Training
  - [x] 8.1 Implement interaction matrix construction in `src/recommender.py`
    - Implement `HybridRecommender.__init__` with config and data directory
    - Implement MovieLens 25M data loading: download `ml-25m` dataset from GroupLens if not present, load `ratings.csv` as implicit feedback (binarize all ratings to 1)
    - Implement user watch history insertion as a new user row in the interaction matrix
    - Build internal index mappings: `tmdb_id_to_internal` and `internal_to_tmdb_id`
    - Cache interaction matrix to `data/interaction_matrix.npz`
    - _Requirements: 5.1, 5.2, 1.5_

  - [x] 8.2 Implement LightFM model training
    - Implement `train(watch_history, progress_callback)` orchestrating the full pipeline: ID resolution → metadata fetch → feature engineering → LightFM training
    - Configure LightFM with WARP loss, `no_components=64`, `epochs=30`
    - Pass Item Feature Matrix as item side features
    - Implement `is_model_fresh()` checking if cached model is < 7 days old
    - Implement model persistence to `data/lightfm_model.pkl` (pickle with index maps)
    - Implement `retrain(watch_history, progress_callback)` for forced retraining
    - Handle watch history change detection to trigger retraining
    - _Requirements: 5.3, 5.4, 5.5, 5.6, 5.7_

  - [ ]* 8.3 Write property test for User Interactions in Interaction Matrix
    - **Property 2: User Interactions in Interaction Matrix**
    - **Validates: Requirements 1.5, 5.2**

  - [ ]* 8.4 Write property test for Implicit Feedback Binarization
    - **Property 9: Implicit Feedback Binarization**
    - **Validates: Requirements 5.1**

  - [ ]* 8.5 Write property test for Model Serialization Round-Trip
    - **Property 10: Model Serialization Round-Trip**
    - **Validates: Requirements 5.4**

  - [ ]* 8.6 Write unit tests for model staleness and hyperparameters
    - Test model < 7 days → load, ≥ 7 days → retrain (Req 5.5)
    - Test watch history change triggers retrain (Req 5.6)
    - Test `no_components >= 64` and `epochs >= 30` (Req 5.7)
    - _Requirements: 5.5, 5.6, 5.7_

- [x] 9. Implement Recommender module — Scoring and Ranking
  - [x] 9.1 Implement scoring, normalization, and ranking in `src/recommender.py`
    - Implement `recommend(n=50)` that predicts scores for all candidates using the trained LightFM model
    - Apply min-max normalization to scale scores to [0.0, 1.0]
    - Rank by descending normalized score and return top-N `RecommendationResult` objects
    - Exclude all movies in the user's watch history from results
    - Implement candidate pool construction (exclude watched, target 5,000+ candidates, cache with 7-day TTL)
    - Log warning if candidate pool < 1,000 after filtering
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 7.2, 7.3, 7.4, 7.5_

  - [x] 9.2 Implement result serialization and deserialization
    - Implement `serialize_results(results, path)` to save recommendations to JSON
    - Implement `deserialize_results(path)` to reload recommendations from JSON
    - Serialize Item Feature Matrix metadata (dimensions, sparsity, feature names sample) to JSON
    - _Requirements: 11.1, 11.2, 11.3, 11.4_

  - [ ]* 9.3 Write property test for Score Normalization, Ranking, and Coverage
    - **Property 11: Score Normalization, Ranking, and Coverage**
    - **Validates: Requirements 6.1, 6.2, 6.3**

  - [ ]* 9.4 Write property test for Watch History Exclusion from Results
    - **Property 12: Watch History Exclusion from Results**
    - **Validates: Requirements 6.4, 7.3**

  - [ ]* 9.5 Write property test for Recommendation Result Serialization Round-Trip
    - **Property 14: Recommendation Result Serialization Round-Trip**
    - **Validates: Requirements 11.1, 11.2, 11.3**

- [x] 10. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 11. Implement Recommendation UI tab in Streamlit
  - [x] 11.1 Add "🎯 Recommendations" tab to `src/app.py`
    - Add a third tab alongside existing "🍿 Watchlist" and "🔍 Quick Lookup" tabs
    - Import and instantiate `HybridRecommender` from `src/recommender.py`
    - Display each recommendation with poster, title, year, runtime, genres, and normalized score (0.0–1.0)
    - Use the same card/grid layout and CSS styling as the existing Watchlist tab
    - _Requirements: 9.1, 9.2_

  - [x] 11.2 Implement streaming availability filter
    - Add a toggle/checkbox to filter recommendations by user's owned streaming services
    - When enabled, query JustWatch via existing `justwatch_query.py` for each displayed recommendation
    - Show provider badges per country consistent with existing Watchlist tab styling
    - _Requirements: 9.3, 9.4_

  - [x] 11.3 Implement pagination and model controls
    - Add pagination or "Load more" button to browse beyond initial results
    - Add "Retrain Model" button that triggers `retrain()` with latest watch history
    - Display progress indicator while recommendations are being computed
    - Show informational message for first-time setup explaining it may take several minutes
    - _Requirements: 9.5, 9.6, 10.4, 10.5_

  - [x] 11.4 Implement caching and performance logic in UI
    - Check for cached model on tab load; use cached if < 7 days old
    - Display "Refreshing recommendation data..." spinner when recomputing
    - Ensure top-50 recommendations load within 15 seconds when model and features are cached
    - _Requirements: 10.1, 10.2, 10.3_

- [x] 12. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document using Hypothesis
- Unit tests validate specific examples and edge cases
- The implementation uses Python throughout (LightFM, Hypothesis, scikit-learn, sentence-transformers)
- MovieLens 25M data is downloaded on first run from GroupLens
- All cached artifacts use a 7-day TTL stored in the `data/` directory

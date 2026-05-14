# Requirements Document

## Introduction

This feature adds a hybrid movie recommendation engine to the existing Letterboxd watchlist streaming availability app. The recommender uses LightFM, a hybrid matrix-factorization model that natively combines implicit user-item interactions with item side features (sparse categorical features from TMDB metadata and dense sentence-transformer plot embeddings). The model trains on MovieLens 25M implicit interactions augmented with the user's Letterboxd watch history, producing a single unified score per candidate movie. Recommendations are presented in a new Streamlit tab alongside the existing Watchlist and Quick Lookup tabs, with optional streaming availability enrichment via the existing JustWatch integration.

## Glossary

- **Recommender**: The hybrid movie recommendation engine that produces ranked movie suggestions using a trained LightFM model
- **LightFM_Model**: The hybrid factorization model (from the `lightfm` library) that learns user and item latent factors while incorporating item side features, trained on implicit feedback (watched/not watched)
- **Taste_Profile**: A user-specific representation within the LightFM_Model, consisting of the user's learned latent factor vector derived from implicit watch history interactions
- **Item_Feature_Matrix**: A combined feature matrix for all candidate movies, consisting of sparse TF-IDF weighted categorical features (genres, directors, top cast, keywords) concatenated with dense 384-dimensional sentence-transformer plot embeddings
- **Watch_History**: The set of movies a user has marked as watched on Letterboxd, treated as implicit positive interactions (no explicit ratings needed)
- **Interaction_Matrix**: A sparse user-item matrix where a 1 indicates the user has watched a movie and 0 indicates no interaction, built from MovieLens 25M implicit data and the user's Watch_History
- **Embedding_Vector**: A 384-dimensional dense vector produced by a sentence-transformer model from a movie's plot overview text, used as a dense item side feature for the LightFM_Model
- **ID_Mapper**: The component that maps between Letterboxd movie slugs, TMDB IDs, and MovieLens IDs to enable cross-dataset lookups
- **Candidate_Pool**: The set of movies eligible for recommendation, excluding movies already in the user's Watch_History
- **Recommendation_UI**: The Streamlit tab that displays ranked recommendations with posters, metadata, scores, and optional streaming availability
- **Feature_Engineer**: The component that constructs the Item_Feature_Matrix by combining sparse TF-IDF categorical features with dense sentence-transformer embeddings for each movie

## Requirements

### Requirement 1: Watch History Ingestion

**User Story:** As a user, I want the recommender to ingest my Letterboxd watch history as implicit feedback, so that the LightFM model can learn my preferences.

#### Acceptance Criteria

1. WHEN the user initiates a recommendation session, THE Recommender SHALL scrape the user's Letterboxd watched films list and produce a Watch_History containing each film's title, year, and slug
2. WHEN a Watch_History is loaded, THE Recommender SHALL resolve each film to a TMDB ID using the existing TMDB search integration
3. IF a film in the Watch_History cannot be resolved to a TMDB ID, THEN THE Recommender SHALL log a warning and exclude that film from the Interaction_Matrix without halting the pipeline
4. THE Recommender SHALL cache resolved TMDB IDs locally so that repeated recommendation sessions do not re-query TMDB for previously resolved films
5. WHEN the Watch_History is resolved, THE Recommender SHALL insert the user's implicit interactions (value 1 for each watched film) into the Interaction_Matrix alongside the MovieLens 25M interactions

### Requirement 2: TMDB Metadata Retrieval

**User Story:** As a user, I want the system to fetch rich metadata for my watched movies and candidate movies, so that item feature engineering has sufficient signal for the LightFM model.

#### Acceptance Criteria

1. WHEN a TMDB ID is resolved for a film, THE Recommender SHALL fetch genres, director names, top 5 billed cast names, keywords, plot overview, and release year from the TMDB API
2. THE Recommender SHALL cache fetched TMDB metadata to a local JSON file so that subsequent sessions reuse cached data and minimize API calls
3. IF the TMDB API returns an error or rate-limits a request, THEN THE Recommender SHALL retry with exponential backoff up to 3 attempts before skipping that film
4. WHEN fetching metadata for candidate movies, THE Recommender SHALL retrieve metadata for popular and well-rated movies from TMDB discovery endpoints to populate the Candidate_Pool

### Requirement 3: Item Feature Engineering — Sparse Categorical Features

**User Story:** As a user, I want the recommender to represent movie metadata as structured features, so that the LightFM model can leverage genre, director, cast, and keyword signals.

#### Acceptance Criteria

1. THE Feature_Engineer SHALL construct sparse TF-IDF weighted feature vectors from categorical features (genres, directors, top cast, keywords) for all movies in the Candidate_Pool and Watch_History
2. THE Feature_Engineer SHALL prune features that appear in fewer than 3 movies to reduce sparsity
3. THE Feature_Engineer SHALL produce one sparse feature vector per movie, suitable for input as item side features to the LightFM_Model
4. FOR ALL movies, parsing the categorical metadata into TF-IDF feature vectors and then reconstructing feature labels SHALL produce equivalent feature sets (round-trip property)

### Requirement 4: Item Feature Engineering — Dense Plot Embeddings

**User Story:** As a user, I want the recommender to capture thematic similarity from plot descriptions, so that the LightFM model can recommend movies with similar stories even when metadata categories differ.

#### Acceptance Criteria

1. THE Feature_Engineer SHALL generate a 384-dimensional Embedding_Vector for each movie's plot overview using a sentence-transformer model (all-MiniLM-L6-v2 or equivalent)
2. IF a movie has no plot overview text, THEN THE Feature_Engineer SHALL use a zero vector of 384 dimensions as the Embedding_Vector for that movie
3. THE Feature_Engineer SHALL cache computed Embedding_Vectors to a local file so that subsequent sessions do not recompute embeddings for previously processed movies
4. THE Feature_Engineer SHALL concatenate each movie's sparse TF-IDF feature vector with its dense Embedding_Vector to produce the final item feature row in the Item_Feature_Matrix

### Requirement 5: LightFM Model Training

**User Story:** As a user, I want the system to train a single hybrid model on implicit feedback and item features, so that I get recommendations that blend collaborative and content signals without manual weight tuning.

#### Acceptance Criteria

1. THE Recommender SHALL construct the Interaction_Matrix from MovieLens 25M data by treating all ratings as implicit feedback (1 for any rated movie, 0 otherwise)
2. THE Recommender SHALL add the user's Watch_History interactions to the Interaction_Matrix as a new user row with value 1 for each watched film that has a valid MovieLens ID mapping
3. THE LightFM_Model SHALL be trained using the WARP (Weighted Approximate-Rank Pairwise) loss function on the Interaction_Matrix with the Item_Feature_Matrix as item side features
4. THE Recommender SHALL persist the trained LightFM_Model to disk so that subsequent sessions load the pre-trained model without retraining
5. WHEN a pre-trained LightFM_Model exists and is less than 7 days old, THE Recommender SHALL load the existing model instead of retraining
6. IF the user's Watch_History has changed since the last training, THEN THE Recommender SHALL retrain the LightFM_Model to incorporate the new interactions
7. THE LightFM_Model SHALL use at least 64 latent components and train for at least 30 epochs

### Requirement 6: Recommendation Scoring and Ranking

**User Story:** As a user, I want a single ranked list of movie recommendations produced by the unified model, so that I get well-rounded suggestions without needing to tune blending weights.

#### Acceptance Criteria

1. WHEN generating recommendations, THE LightFM_Model SHALL predict scores for all movies in the Candidate_Pool for the user
2. THE Recommender SHALL normalize predicted scores to the range 0.0 to 1.0 by applying min-max scaling across all candidate predictions
3. THE Recommender SHALL rank candidate movies by descending normalized score and return the top N results (default N=50)
4. THE Recommender SHALL exclude all movies present in the user's Watch_History from the ranked results
5. FOR ALL candidate movies in the Candidate_Pool, the predicted score for a watched movie SHALL be higher on average than the predicted score for a random unwatched movie (sanity check property)

### Requirement 7: Candidate Pool Construction

**User Story:** As a user, I want the recommendation engine to consider a broad and relevant set of candidate movies, so that recommendations are not limited to a narrow slice of cinema.

#### Acceptance Criteria

1. THE Recommender SHALL build the Candidate_Pool from TMDB discovery endpoints, including top-rated movies, popular movies, and movies sharing genres with the user's Watch_History
2. THE Recommender SHALL target a Candidate_Pool size of at least 5,000 movies
3. THE Recommender SHALL exclude movies already in the user's Watch_History from the Candidate_Pool
4. THE Recommender SHALL cache the Candidate_Pool metadata locally and refresh it no more than once per week
5. IF the Candidate_Pool contains fewer than 1,000 movies after filtering, THEN THE Recommender SHALL log a warning indicating limited candidate coverage

### Requirement 8: ID Mapping Across Datasets

**User Story:** As a user, I want the system to reliably link movies across Letterboxd, TMDB, and MovieLens, so that the LightFM model can leverage the external interaction dataset.

#### Acceptance Criteria

1. THE ID_Mapper SHALL load the MovieLens links.csv file to establish a mapping between MovieLens IDs and TMDB IDs
2. THE ID_Mapper SHALL resolve Letterboxd slugs to TMDB IDs using the existing TMDB search-by-title-and-year approach
3. WHEN a TMDB ID has a corresponding MovieLens ID in the links file, THE ID_Mapper SHALL return the MovieLens ID
4. IF a TMDB ID has no corresponding MovieLens ID, THEN THE ID_Mapper SHALL return None and the Recommender SHALL exclude that movie from the Interaction_Matrix training data
5. FOR ALL TMDB IDs present in the links file, mapping from TMDB ID to MovieLens ID and then back to TMDB ID SHALL return the original TMDB ID (round-trip property)

### Requirement 9: Recommendation UI Tab

**User Story:** As a user, I want to view recommendations in a dedicated tab within the existing Streamlit app, so that I can browse suggestions alongside my watchlist.

#### Acceptance Criteria

1. THE Recommendation_UI SHALL appear as a new tab labeled "🎯 Recommendations" alongside the existing "🍿 Watchlist" and "🔍 Quick Lookup" tabs
2. THE Recommendation_UI SHALL display each recommended movie with its poster, title, year, runtime, and recommendation score (normalized 0.0 to 1.0)
3. THE Recommendation_UI SHALL provide a filter to show only movies available on the user's owned streaming services using the existing JustWatch integration
4. WHEN the streaming filter is enabled, THE Recommendation_UI SHALL query JustWatch for each displayed recommendation and show provider badges per country, consistent with the existing Watchlist tab styling
5. THE Recommendation_UI SHALL support pagination or infinite scroll to browse beyond the initial set of results
6. THE Recommendation_UI SHALL display a "Retrain Model" button that triggers retraining of the LightFM_Model with the latest Watch_History

### Requirement 10: Performance and Caching

**User Story:** As a user, I want recommendations to load within a reasonable time, so that the experience is practical for interactive use.

#### Acceptance Criteria

1. WHEN a pre-trained LightFM_Model and cached item features exist, THE Recommender SHALL generate the top 50 recommendations within 15 seconds of the user requesting them
2. THE Recommender SHALL cache the trained LightFM_Model, computed Embedding_Vectors, Item_Feature_Matrix, TMDB metadata, and ID mappings to local files in the data directory
3. WHEN cached data exists and is less than 7 days old, THE Recommender SHALL use cached data instead of recomputing
4. THE Recommendation_UI SHALL display a progress indicator while recommendations are being computed
5. IF the initial model training or embedding computation is required, THEN THE Recommendation_UI SHALL inform the user that first-time setup may take several minutes

### Requirement 11: Score Serialization and Deserialization

**User Story:** As a developer, I want recommendation scores and intermediate results to be serializable, so that they can be cached, inspected, and reloaded across sessions.

#### Acceptance Criteria

1. THE Recommender SHALL serialize recommendation results (movie ID, title, year, recommendation score) to a JSON file
2. THE Recommender SHALL deserialize previously saved recommendation results from JSON and reconstruct equivalent score objects
3. FOR ALL valid recommendation result objects, serializing to JSON and then deserializing SHALL produce an object with equivalent field values (round-trip property)
4. THE Recommender SHALL serialize the Item_Feature_Matrix metadata (feature names, dimensions, sparsity statistics) to a JSON file for inspection

# Project Handoff Summary

> Handoff document for a future AI agent / developer picking up this project.
> Written June 18, 2026. The original developer is losing access to this machine,
> so this captures the state of work, decisions made, and open items.

## Project Overview

**Repo:** `letterboxd-justwatch-vpn` (GitHub: `bucanero2010/letterboxd-justwatch-vpn`)
**Stack:** Python, Streamlit
**Purpose:** Two things in one app:
1. Track where a Letterboxd watchlist is streaming across countries/services (JustWatch data).
2. A hybrid movie recommender that learns from the user's Letterboxd watch history.

### App structure (`src/app.py`)
Streamlit app with tabs: Watchlist availability, Quick Lookup, and Recommendations.

### Recommender (`src/recommender.py`)
Hybrid recommender using **LightFM** with **WARP loss**, 64 components, 5 epochs.
- Interaction matrix built from **MovieLens 25M** (`data/ml-25m/`) — ~59,047 items.
- User's Letterboxd watch history (`data/watch_history_cache.json`, ~953 films) is
  inserted as one extra user row, weighted by **z-score ratings** (relative to the
  user's own rating mean/std), not binary.
- Item side features via `src/feature_engineer.py`: TF-IDF tokens + PCA-reduced
  (384→30 dims) sentence-transformer plot embeddings.
- TMDB metadata cache: `data/tmdb_metadata_cache.json` (~58K movies).
- ID resolution: `src/id_mapper.py` resolves Letterboxd slug → TMDB ID, and maps
  TMDB ↔ MovieLens IDs via `links.csv`. Slug→TMDB cached in `data/tmdb_id_cache.json`.

## Work Done In This Session

### 1. `expand_and_retrain()` — IMPLEMENTED, NOT MERGED TO MAIN
Lives on the **local branch `feature/expand-and-retrain`** (commit `9b64d3c`).
**This branch was never pushed to remote — see Open Items.**

Problem it solves: ~190 recent films in the user's watch history aren't in MovieLens
(see `data/unmapped_films.json`), so the model couldn't learn from them.

What the new `HybridRecommender.expand_and_retrain()` does:
1. Loads MovieLens ratings → base interaction matrix.
2. Builds standard index mappings from `links.csv`.
3. Resolves all watch history slugs to TMDB IDs (mostly cached already).
4. Identifies unmapped films (have a TMDB ID but no MovieLens column).
5. **Expands the interaction matrix** by appending new zero-columns for each unmapped
   film (MovieLens users get 0; only the user row gets values).
6. Updates `_tmdb_id_to_internal` / `_internal_to_tmdb_id` with the new column indices.
7. Inserts user watch history (now including the formerly-unmapped films) with z-scores.
8. Deletes stale feature caches (`item_features.npz`, `plot_embeddings.npz`,
   `item_features_aligned.npz`) so they rebuild.
9. Fetches TMDB metadata + rebuilds features for the expanded item set.
10. Full LightFM retrain (5 epochs, WARP, 64 components).
11. Saves model, clears `unmapped_films.json`.

In `src/app.py`, the existing "📥 Expand & Retrain" button was rewired: it used to fall
through to a generic full retrain; it now calls `expand_and_retrain()`. The button
handler (`_expand_clicked`) was separated from `_full_retrain`.

### 2. Added Filmin to owned streaming services — MERGED & PUSHED TO MAIN
Commit `c819375` (now on remote as part of `0c2d459`). Added `"Filmin": ["Filmin"]`
to `OWNED_SERVICES_MAP` in `src/app.py`. All owned services are selected by default.

Current owned services: Netflix, Prime (Amazon Prime Video), HBO (HBO Max),
Apple (Apple TV), Disney (Disney Plus), Youtube, RTVE, Filmin.

### 3. Git history cleanup
Earlier in the session `main` had 5 unpushed commits + uncommitted expand work.
Per request, all of that was moved to `feature/expand-and-retrain` and `main` was
reset to match `origin/main`. Then Filmin was committed onto a fresh `main`,
rebased on top of new remote commits, and pushed.

## Open Items / TODO

- **PUSH the `feature/expand-and-retrain` branch.** It only exists locally and holds
  the entire recommender system (the original 5 commits) PLUS `expand_and_retrain()`.
  If this machine is lost before pushing, that work is gone. Run:
  `git push -u origin feature/expand-and-retrain`
- **Test `expand_and_retrain()`** end to end. Fastest path: run the app
  (`source venv/bin/activate && python3 -m streamlit run src/app.py`), click
  "📥 Expand & Retrain", watch the log. Afterward the unmapped-films expander should
  show 0 films. Full run re-loads MovieLens (~30s) and retrains (~2–3 min).
- **CI note:** GitHub Actions uses Python 3.11, default Playwright (no
  `channel="chromium"`). The local scraper path in `app.py` uses
  `channel="chromium"` — keep that in mind if wiring scraping into CI.
- Consider adding a unit test for the matrix-expansion logic (mock MovieLens load and
  TMDB fetches; assert column count grows by the number of unmapped films and that the
  new indices land in the mapping dicts). No tests cover `expand_and_retrain()` yet.

## Key Files Reference

| File | Purpose |
|---|---|
| `src/app.py` | Streamlit UI, filters, owned-services map, button handlers |
| `src/recommender.py` | `HybridRecommender`: train/retrain/expand_and_retrain/recommend |
| `src/feature_engineer.py` | TF-IDF + embedding feature matrix |
| `src/id_mapper.py` | slug↔TMDB↔MovieLens ID resolution |
| `src/tmdb_metadata.py` | TMDB metadata fetching + cache |
| `data/watch_history_cache.json` | ~953 watched films with ratings |
| `data/unmapped_films.json` | films not in MovieLens (expansion targets) |
| `data/tmdb_id_cache.json` | slug → TMDB ID cache |
| `data/ml-25m/` | MovieLens 25M ratings + links |

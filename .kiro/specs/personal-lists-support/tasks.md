# Implementation Plan: Personal Lists Support

## Overview

Extend the letterboxd-justwatch-vpn tool from a single-source (watchlist-only) scanner to a multi-source scanner that auto-discovers and processes all of a user's personal Letterboxd lists. Implementation proceeds bottom-up: scraper additions, then scanner restructuring, then UI changes, with property tests validating correctness at each layer.

## Tasks

- [x] 1. Add `discover_lists()` to `letterbox_scraper.py`
  - [x] 1.1 Implement the `discover_lists(username, sleep, max_pages)` function
    - Fetch `https://letterboxd.com/{username}/lists/` using the existing `cloudscraper` session
    - Parse list entries from the HTML to extract list name, URL, and slug
    - Handle pagination (follow "next" links, up to `max_pages`)
    - Return a `list[dict]` with keys `name`, `url`, `slug`
    - Log a warning and return an empty list if the page is unreachable or returns an HTTP error
    - _Requirements: 1.1, 1.2, 1.5, 1.6_

  - [ ]* 1.2 Write unit tests for `discover_lists()`
    - Mock HTML responses for a lists page with multiple lists across pages
    - Test empty lists page returns empty list and logs info
    - Test unreachable page returns empty list and logs warning
    - _Requirements: 1.1, 1.2, 1.5, 1.6_

- [x] 2. Add per-source history helpers to `main.py`
  - [x] 2.1 Implement `get_history_path(source_key)`, `load_history(source_key)`, and `save_history(source_key, history_set)`
    - `get_history_path` returns `DATA_DIR / f"seen_{source_key}.json"`
    - `load_history` reads the JSON file into a set, returns empty set if missing or corrupt
    - `save_history` writes the set as a JSON list
    - Remove the old module-level `get_history()` and `save_history()` functions and the `WATCHLIST_HISTORY` constant
    - _Requirements: 2.1, 2.2, 2.3, 2.4_

  - [ ]* 2.2 Write property test for history path derivation
    - **Property 1: History path derivation**
    - For any valid source key, `get_history_path(key)` returns `DATA_DIR / f"seen_{key}.json"`. Specifically, `"watchlist"` → `seen_watchlist.json`, `"list_<slug>"` → `seen_list_<slug>.json`.
    - **Validates: Requirements 2.1, 2.2, 2.3**

- [x] 3. Checkpoint — Verify scraper and history helpers
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Restructure `main.py` for multi-source scanning
  - [x] 4.1 Build the sources list in `main()`
    - Call `discover_lists(USERNAME)` to get personal lists
    - Construct a sources list: watchlist entry (`key="watchlist"`) plus one entry per discovered list (`key="list_{slug}"`)
    - If `discover_lists` fails or returns empty, continue with watchlist only
    - _Requirements: 1.3, 1.4, 1.5, 1.6_

  - [x] 4.2 Implement per-source scanning loop
    - For each source, load its history via `load_history(source['key'])`
    - Apply full-scan vs daily-scan logic independently per source
    - Scrape films using the existing `scrape_films()` with the source URL
    - Save history via `save_history(source['key'], ...)` after scanning
    - If an individual list URL fails to scrape, log a warning and continue with remaining sources
    - _Requirements: 2.4, 3.1, 3.3_

  - [x] 4.3 Implement cross-source deduplication and source tagging
    - Merge films from all sources into a single collection, deduplicating by `(title, year)`
    - Track which source names each film belongs to using a `dict[film_id, set[source_name]]` mapping
    - Query JustWatch only for unique films
    - _Requirements: 3.2, 3.5_

  - [x] 4.4 Add `source` column to CSV output
    - For each output row, populate the `source` column with comma-separated source names
    - Ensure the column is present in both full-scan and daily-scan code paths
    - _Requirements: 3.4, 3.5_

  - [x] 4.5 Update pruning logic for multi-source
    - Build a combined set of current film IDs from all discovered sources
    - Prune rows from the existing CSV where the film ID is no longer in any current source
    - _Requirements: 4.1, 4.2, 4.3_

  - [ ]* 4.6 Write property test for deduplication
    - **Property 2: Deduplication preserves all unique films**
    - For any collection of film lists, after dedup by (title, year), the output contains exactly one entry per unique pair, and the set of unique pairs equals the union across all inputs.
    - **Validates: Requirements 3.2, 4.1**

  - [ ]* 4.7 Write property test for multi-source tagging
    - **Property 3: Multi-source tagging correctness**
    - For any film appearing in N sources (N ≥ 1), the `source` field contains exactly the set of source names where that film appears.
    - **Validates: Requirements 3.5**

  - [ ]* 4.8 Write property test for pruning
    - **Property 4: Pruning removes only stale films**
    - For any existing DataFrame and current film ID set: (a) every remaining row's film ID is in the current set, (b) no row whose film ID is in the current set is removed.
    - **Validates: Requirements 4.2, 4.3**

- [x] 5. Checkpoint — Verify multi-source scanning
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Add source filter to Streamlit UI in `app.py`
  - [x] 6.1 Implement source filter dropdown in the sidebar
    - Check if `source` column exists in the DataFrame
    - If present, add a "📋 Sources" multiselect with "📋 All sources" default plus one option per distinct source value
    - Filter the DataFrame based on selection
    - If `source` column is absent, skip the filter entirely (backward compatibility)
    - _Requirements: 5.1, 5.2, 5.3, 5.5_

  - [x] 6.2 Deduplicate display when "All sources" is selected
    - When "All sources" is active, deduplicate the grid display by (title, year) so films appearing in multiple sources show once
    - _Requirements: 5.4_

  - [ ]* 6.3 Write property test for source filter
    - **Property 5: Source filter returns matching rows**
    - For any DataFrame with a `source` column and any selected source name, filtering returns only and all rows where `source` contains the selected name.
    - **Validates: Requirements 5.3**

  - [ ]* 6.4 Write property test for "All sources" deduplication
    - **Property 6: "All sources" deduplicates by title and year**
    - For any DataFrame with a `source` column, when "All sources" is selected, the result contains at most one entry per unique (title, year) and every unique pair is present.
    - **Validates: Requirements 5.4**

- [x] 7. Final checkpoint — Full integration verification
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Property tests use `hypothesis` (Python PBT library) with a minimum of 100 iterations
- Checkpoints ensure incremental validation
- History files for removed lists are intentionally retained (Requirement 2.5)

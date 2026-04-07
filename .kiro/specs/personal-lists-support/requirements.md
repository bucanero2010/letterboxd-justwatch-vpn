# Requirements Document

## Introduction

The letterboxd-justwatch-vpn tool currently only scrapes the user's Letterboxd watchlist to find streaming availability across countries. This feature extends the tool to automatically discover and process all of the user's personal Letterboxd lists (scraped from their profile's lists page, e.g. `https://letterboxd.com/bucanero2010/lists/`), allowing users to check streaming availability for films across all their curated lists alongside the watchlist without manual configuration.

## Glossary

- **Scanner**: The main orchestration module (`main.py`) that coordinates scraping, querying, and output generation
- **Scraper**: The Letterboxd scraping module (`letterbox_scraper.py`) that extracts film data from paginated Letterboxd pages
- **Config**: The JSON configuration file (`config.json`) that stores user preferences and credentials
- **Lists_Page**: The Letterboxd profile lists page (e.g. `https://letterboxd.com/<user>/lists/`) from which the Scraper discovers all of the user's personal lists
- **History_Store**: The JSON-based persistence layer (`seen_watchlist.json` and per-list history files) that tracks previously scanned films
- **Source**: A Letterboxd URL from which films are scraped — either the watchlist or a personal list
- **Output_File**: The CSV file (`unwatched_by_country.csv`) containing aggregated streaming availability results
- **Streamlit_App**: The web UI (`app.py`) that displays streaming availability results with filters

## Requirements

### Requirement 1: Auto-Discover Personal Lists

**User Story:** As a user, I want the tool to automatically discover all my Letterboxd lists from my profile, so that I do not need to manually enter list URLs.

#### Acceptance Criteria

1. THE Scraper SHALL provide a function to scrape the user's Lists_Page (`https://letterboxd.com/<user>/lists/`) and return a collection of list names and URLs
2. THE Scraper SHALL handle pagination on the Lists_Page to discover all lists (not just the first page)
3. WHEN the Scanner starts, THE Scanner SHALL call the list-discovery function using the `letterboxd_user` value from the Config to obtain all personal lists
4. THE Scanner SHALL process each discovered list URL in addition to the watchlist
5. IF the Lists_Page returns no lists, THEN THE Scanner SHALL log an informational message and process only the watchlist
6. IF the Lists_Page is unreachable or returns an error, THEN THE Scanner SHALL log a warning and continue processing only the watchlist

### Requirement 2: Per-Source History Tracking

**User Story:** As a user, I want the tool to track scan history independently for each source, so that daily incremental scans work correctly across multiple sources.

#### Acceptance Criteria

1. THE History_Store SHALL maintain a separate history file for each Source, using the naming convention `seen_<source_key>.json` where `source_key` is derived from the Source identifier
2. WHEN processing the watchlist, THE History_Store SHALL use `seen_watchlist.json` as the history file (preserving backward compatibility)
3. WHEN processing a personal list with slug `<slug>`, THE History_Store SHALL use `seen_list_<slug>.json` as the history file
4. THE Scanner SHALL load and save history independently for each Source during a scan run
5. WHEN a list is no longer discovered from the user's profile, THE History_Store SHALL retain the corresponding history file (no automatic deletion)

### Requirement 3: Multi-Source Scanning

**User Story:** As a user, I want the Scanner to iterate over all configured sources and aggregate results, so that I see streaming availability for films from all my lists in one output.

#### Acceptance Criteria

1. THE Scanner SHALL iterate over each discovered Source (watchlist plus all auto-discovered personal lists) and scrape films from each
2. THE Scanner SHALL deduplicate films across Sources before querying streaming availability, using the combination of film title and year as the unique identifier
3. THE Scanner SHALL apply the existing full-scan vs. daily-scan logic (Sunday/1st-of-month triggers) independently per Source using each Source's own history
4. THE Output_File SHALL contain a `source` column indicating which Source each row originated from
5. WHEN a film appears in multiple Sources, THE Output_File SHALL tag the row with all applicable Source names in the `source` column

### Requirement 4: Multi-Source Pruning

**User Story:** As a user, I want films removed from a source to be pruned from the output, so that the CSV stays in sync with my current Letterboxd lists.

#### Acceptance Criteria

1. THE Scanner SHALL build a combined set of current film identifiers from all discovered Sources
2. WHEN pruning the Output_File, THE Scanner SHALL remove rows for films that no longer appear in any discovered Source
3. WHEN a list is deleted from the user's Letterboxd profile (and thus no longer discovered), THE Scanner SHALL prune rows tagged exclusively with that Source from the Output_File on the next run

### Requirement 5: Source Filter in Streamlit UI

**User Story:** As a user, I want to filter the displayed results by individual list or see everything merged together, so that I can focus on a specific list or browse all films at once.

#### Acceptance Criteria

1. WHEN the Output_File contains a `source` column, THE Streamlit_App SHALL display a source filter dropdown in the sidebar with an "All sources" option and one option per distinct Source value
2. THE Streamlit_App SHALL default the source filter selection to "All sources", showing films from every Source merged together
3. WHEN the user selects a specific Source from the filter, THE Streamlit_App SHALL display only films matching that single Source
4. WHEN the user selects "All sources", THE Streamlit_App SHALL display all films from every Source without duplication (deduplicated by title and year)
5. IF the Output_File does not contain a `source` column, THEN THE Streamlit_App SHALL skip the source filter and display all rows (backward compatibility)

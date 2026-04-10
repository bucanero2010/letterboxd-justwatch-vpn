# Implementation Plan: Services I Own Filter

## Overview

Add a "Services I own" checkbox filter to the Streamlit sidebar in `src/app.py`. The filter uses a predefined mapping of service labels to provider substrings, renders as a popover with checkboxes (following the existing toggle_all pattern), and applies substring-based filtering as an AND condition in the existing pipeline. All changes are scoped to `src/app.py`, with optional property-based tests using `hypothesis`.

## Tasks

- [x] 1. Add the OWNED_SERVICES_MAP constant and filter helper
  - [x] 1.1 Define the `OWNED_SERVICES_MAP` dictionary in `src/app.py`
    - Add the module-level constant after the existing helpers section
    - Include entries for Netflix, Prime, HBO, Apple, Disney, Youtube, and RTVE with their provider substrings
    - _Requirements: 1.1, 1.2, 1.3_

  - [ ]* 1.2 Write property test: Map structure validity
    - **Property 1: Map structure validity**
    - Verify that every key in `OWNED_SERVICES_MAP` maps to a non-empty list of non-empty strings
    - **Validates: Requirement 1.2**

- [x] 2. Add the "Services I own" sidebar UI
  - [x] 2.1 Initialize session state for owned services
    - Add session state initialization for `all_owned` (default `False`) and `owned_{label}` keys (default `False` for each label)
    - Place initialization after the existing streaming services popover section
    - _Requirements: 7.1, 7.2, 2.4_

  - [x] 2.2 Render the "Services I own" popover with checkboxes
    - Add `st.sidebar.popover("🏠 Services I own")` between the Streaming services popover and the Sources dropdown
    - Include a "Select all" checkbox wired to the existing `toggle_all` callback with `group_prefix="owned"`, `items=list(OWNED_SERVICES_MAP.keys())`, `select_all_key="all_owned"`
    - Render one checkbox per entry in `OWNED_SERVICES_MAP`
    - Collect `selected_owned_services` list from session state
    - _Requirements: 2.1, 2.2, 2.3, 3.1, 3.2_

  - [ ]* 2.3 Write property test: Toggle all sets all checkboxes
    - **Property 2: Toggle all sets all checkboxes**
    - For any initial combination of checkbox states and any boolean value V, setting the select-all toggle to V results in every individual checkbox being set to V
    - **Validates: Requirements 3.1, 3.2**

- [x] 3. Implement owned services filtering logic
  - [x] 3.1 Add the owned-services filter to the filtering pipeline
    - After the existing streaming services filter and before the source filter, add the owned-services filter block
    - If `selected_owned_services` is non-empty, flatten substrings from `OWNED_SERVICES_MAP` for selected labels, build an OR mask using `str.contains(pattern, regex=False)`, and apply the mask to `filtered_df`
    - If no owned services are checked, pass through without filtering
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 5.1, 5.2, 5.3, 6.1_

  - [ ]* 3.2 Write property test: Pass-through when no services selected
    - **Property 3: Pass-through when no services selected**
    - For any DataFrame with a provider column, if no owned service checkboxes are checked, the filter returns a DataFrame identical to the input
    - **Validates: Requirement 4.1**

  - [ ]* 3.3 Write property test: Subset guarantee
    - **Property 4: Subset guarantee**
    - For any DataFrame and any non-empty selection of owned services, every row in the filtered output has a provider value containing at least one substring from the selected services
    - **Validates: Requirement 4.2**

  - [ ]* 3.4 Write property test: No false exclusions
    - **Property 5: No false exclusions**
    - For any DataFrame and any non-empty selection of owned services, every input row whose provider contains a matching substring appears in the filtered output
    - **Validates: Requirements 4.3, 5.1, 5.3**

  - [ ]* 3.5 Write property test: Check-uncheck round-trip
    - **Property 6: Check-uncheck round-trip**
    - For any DataFrame and any single owned service, filtering with that service checked then unchecked produces the same result as the original unfiltered DataFrame
    - **Validates: Requirement 7.3**

- [x] 4. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- All changes are scoped to `src/app.py` (and a test file for optional property tests)
- Property tests use the `hypothesis` library
- Each task references specific requirements for traceability

# Requirements Document

## Introduction

This document defines the requirements for the "Services I Own" filter feature. The feature adds a checkbox-based sidebar filter to the Streamlit application that lets users mark which streaming services they subscribe to. When services are selected, the movie grid filters to show only movies available on those services. The filter uses a predefined mapping of short labels to provider substrings and composes with the existing filtering pipeline.

## Glossary

- **App**: The Streamlit web application defined in `src/app.py` that displays the movie watchlist grid.
- **Sidebar**: The Streamlit sidebar panel containing all filter controls.
- **Owned_Services_Map**: A module-level dictionary mapping short service labels (e.g., "Prime") to lists of provider substrings (e.g., ["Amazon Prime Video"]).
- **Owned_Services_Popover**: The sidebar UI popover containing checkboxes for each predefined streaming service.
- **Filter_Pipeline**: The chain of filters (country, streaming services, owned services, source) applied sequentially to the DataFrame before rendering the movie grid.
- **Provider_Column**: The `provider` column in the CSV DataFrame containing streaming service names.
- **Select_All_Toggle**: A checkbox that, when toggled, sets all individual service checkboxes to the same checked/unchecked state.

## Requirements

### Requirement 1: Owned Services Mapping

**User Story:** As a developer, I want a predefined mapping of service labels to provider substrings, so that the filter can match CSV provider values using short, user-friendly names.

#### Acceptance Criteria

1. THE Owned_Services_Map SHALL define entries for Netflix, Prime, HBO, Apple, Disney, Youtube, and RTVE.
2. WHEN a label key is looked up in the Owned_Services_Map, THE Owned_Services_Map SHALL return a non-empty list of non-empty provider substrings for that label.
3. THE Owned_Services_Map SHALL use substring values that match the provider names present in the CSV data (e.g., "Amazon Prime Video" for "Prime", "HBO Max" for "HBO").

### Requirement 2: Sidebar UI Rendering

**User Story:** As a user, I want to see a "Services I own" popover in the sidebar with checkboxes for each predefined service, so that I can quickly indicate which services I subscribe to.

#### Acceptance Criteria

1. WHEN the App loads, THE Owned_Services_Popover SHALL render inside the Sidebar after the Streaming services popover and before the Sources dropdown.
2. THE Owned_Services_Popover SHALL display one checkbox for each entry in the Owned_Services_Map.
3. THE Owned_Services_Popover SHALL display a Select_All_Toggle checkbox above the individual service checkboxes.
4. WHEN the App loads for the first time, THE Owned_Services_Popover SHALL initialize all service checkboxes as unchecked.

### Requirement 3: Select All Toggle Behavior

**User Story:** As a user, I want a "Select all" toggle in the Services I own popover, so that I can quickly check or uncheck all services at once.

#### Acceptance Criteria

1. WHEN the user checks the Select_All_Toggle, THE Owned_Services_Popover SHALL set all individual service checkboxes to checked.
2. WHEN the user unchecks the Select_All_Toggle, THE Owned_Services_Popover SHALL set all individual service checkboxes to unchecked.

### Requirement 4: Owned Services Filtering Logic

**User Story:** As a user, I want the movie grid to show only movies available on my selected services, so that I can focus on content I can actually watch.

#### Acceptance Criteria

1. WHEN no owned service checkboxes are checked, THE Filter_Pipeline SHALL pass all rows through without removing any based on owned services.
2. WHEN one or more owned service checkboxes are checked, THE Filter_Pipeline SHALL retain only rows where the Provider_Column contains at least one substring from the selected services' Owned_Services_Map entries.
3. WHEN one or more owned service checkboxes are checked, THE Filter_Pipeline SHALL retain every row whose Provider_Column contains a matching substring from the selected services (no false exclusions).
4. THE Filter_Pipeline SHALL apply the owned services filter as an AND condition with the existing country, streaming services, and source filters.

### Requirement 5: Substring Matching Behavior

**User Story:** As a user, I want the filter to match provider name variants (e.g., "Amazon Prime Video Free" matches "Prime"), so that I see all relevant content for my services.

#### Acceptance Criteria

1. WHEN filtering by an owned service, THE Filter_Pipeline SHALL use substring matching (not exact equality) against the Provider_Column.
2. WHEN filtering by an owned service, THE Filter_Pipeline SHALL use non-regex matching to avoid treating provider substrings as regular expressions.
3. WHEN multiple owned services are checked, THE Filter_Pipeline SHALL combine their substrings using OR logic so that a row matching any selected service is retained.

### Requirement 6: Empty Results Handling

**User Story:** As a user, I want clear feedback when my owned service selections produce no results, so that I know to adjust my filters.

#### Acceptance Criteria

1. WHEN the owned services filter produces zero matching rows, THE App SHALL display the message "😕 No movies match your filters."

### Requirement 7: Session State Management

**User Story:** As a developer, I want the owned services filter to use Streamlit session state consistently, so that checkbox states persist across reruns and follow the existing pattern.

#### Acceptance Criteria

1. THE App SHALL store each owned service checkbox state using the key pattern `owned_{label}` in Streamlit session state.
2. THE App SHALL store the Select_All_Toggle state using the key `all_owned` in Streamlit session state.
3. WHEN the user checks and then unchecks the same service, THE Filter_Pipeline SHALL return to the same filtered state as before the check (idempotent round-trip).

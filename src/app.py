import streamlit as st
import pandas as pd
from pathlib import Path

st.set_page_config(
    page_title="Global Watchlist",
    layout="wide",
    page_icon="🍿"
)

# =========================
# 🎨 CUSTOM CSS
# =========================
st.markdown("""
<style>
/* Dark card styling */
div[data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlock"] {
    border-radius: 12px;
}

/* Movie title styling */
.movie-title {
    font-size: 0.9rem;
    font-weight: 600;
    line-height: 1.3;
    margin: 6px 0 2px 0;
    color: inherit;
}

.movie-meta {
    font-size: 0.75rem;
    opacity: 0.7;
    margin-bottom: 6px;
}

/* Provider badge */
.provider-badge {
    display: inline-block;
    padding: 2px 8px;
    margin: 2px;
    border-radius: 12px;
    font-size: 0.7rem;
    background: rgba(99, 102, 241, 0.15);
    border: 1px solid rgba(99, 102, 241, 0.3);
    color: inherit;
}

/* Country header in availability */
.country-header {
    font-size: 0.8rem;
    font-weight: 600;
    margin: 8px 0 4px 0;
}

/* Stats bar */
.stats-bar {
    display: flex;
    gap: 24px;
    padding: 12px 0;
    margin-bottom: 8px;
    border-bottom: 1px solid rgba(128, 128, 128, 0.2);
}

.stat-item {
    text-align: center;
}

.stat-value {
    font-size: 1.5rem;
    font-weight: 700;
    color: #6366f1;
}

.stat-label {
    font-size: 0.75rem;
    opacity: 0.6;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

/* Poster hover effect */
div[data-testid="stImage"] img {
    border-radius: 8px;
    transition: transform 0.2s ease, box-shadow 0.2s ease;
}

div[data-testid="stImage"] img:hover {
    transform: scale(1.03);
    box-shadow: 0 8px 25px rgba(0, 0, 0, 0.3);
}

/* Search input */
div[data-testid="stTextInput"] input {
    border-radius: 20px !important;
    padding-left: 16px !important;
}

/* Filter tags */
.filter-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    padding: 8px 0;
}

.filter-tag {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 14px;
    font-size: 0.72rem;
    background: rgba(99, 102, 241, 0.12);
    border: 1px solid rgba(99, 102, 241, 0.25);
    color: inherit;
    opacity: 0.85;
}

/* Expander styling */
div[data-testid="stExpander"] {
    border-radius: 8px;
    border: 1px solid rgba(128, 128, 128, 0.15);
}
</style>
""", unsafe_allow_html=True)

# =========================
# 🍿 HEADER + TABS
# =========================
tab_watchlist, tab_lookup = st.tabs(["🍿 Watchlist", "🔍 Quick Lookup"])

# =========================
# 📁 PATHING
# =========================
BASE_DIR = Path(__file__).resolve().parent.parent
file_path = BASE_DIR / "data" / "unwatched_by_country.csv"

if not file_path.exists():
    st.error("❌ CSV file not found. Run your scraper first!")
    st.stop()

df = pd.read_csv(file_path)

# =========================
# 🧠 HELPERS
# =========================
def country_to_flag(code: str) -> str:
    code = code.upper()
    if code == "UK":
        code = "GB"
    if len(code) != 2:
        return code
    return "".join(chr(ord(c) + 127397) for c in code)

def format_runtime(runtime):
    if pd.notna(runtime):
        hours = int(runtime) // 60
        mins = int(runtime) % 60
        return f"{hours}h {mins}m" if hours else f"{mins}m"
    return ""

# =========================
# 🏠 OWNED SERVICES MAP
# =========================
OWNED_SERVICES_MAP: dict[str, list[str]] = {
    "Netflix":  ["Netflix"],
    "Prime":    ["Amazon Prime Video"],
    "HBO":      ["HBO Max"],
    "Apple":    ["Apple TV"],
    "Disney":   ["Disney Plus"],
    "Youtube":  ["YouTube"],
    "RTVE":     ["RTVE"],
}

# =========================
# 🎛️ SIDEBAR FILTERS
# =========================
st.sidebar.markdown("## Filters")

def toggle_all(group_prefix, items, select_all_key):
    val = st.session_state[select_all_key]
    for item in items:
        st.session_state[f"{group_prefix}_{item}"] = val

# --- 🌍 Countries ---
countries = sorted(df["country"].unique().tolist())

if "all_countries" not in st.session_state:
    st.session_state["all_countries"] = True
    for c in countries:
        st.session_state[f"country_{c}"] = True

with st.sidebar.popover("🌍 Countries", use_container_width=True):
    st.checkbox(
        "Select all", key="all_countries",
        on_change=toggle_all, args=("country", countries, "all_countries")
    )
    for c in countries:
        st.checkbox(f"{country_to_flag(c)} {c}", key=f"country_{c}")

selected_countries = [c for c in countries if st.session_state.get(f"country_{c}", True)]
if not selected_countries:
    selected_countries = countries

# --- 📺 Services ---
country_filtered_df = df[df["country"].isin(selected_countries)]
services = sorted(country_filtered_df["provider"].unique().tolist())

if "all_services" not in st.session_state:
    st.session_state["all_services"] = True
    for s in services:
        st.session_state[f"service_{s}"] = True

with st.sidebar.popover("📺 Streaming services", use_container_width=True):
    st.checkbox(
        "Select all", key="all_services",
        on_change=toggle_all, args=("service", services, "all_services")
    )
    with st.container(height=300):
        for s in services:
            st.checkbox(s, key=f"service_{s}")

selected_services = [s for s in services if st.session_state.get(f"service_{s}", True)]
if not selected_services:
    selected_services = services

# --- 🏠 Services I own ---
owned_labels = list(OWNED_SERVICES_MAP.keys())

if "all_owned" not in st.session_state:
    st.session_state["all_owned"] = True
    for label in owned_labels:
        st.session_state[f"owned_{label}"] = True

with st.sidebar.popover("🏠 Services I own", use_container_width=True):
    st.checkbox(
        "Select all", key="all_owned",
        on_change=toggle_all, args=("owned", owned_labels, "all_owned")
    )
    for label in owned_labels:
        st.checkbox(label, key=f"owned_{label}")

selected_owned_services = [label for label in owned_labels if st.session_state.get(f"owned_{label}", False)]

# --- 📋 Sources (multi-select) ---
has_source_column = "source" in df.columns
selected_sources = []

if has_source_column:
    source_filtered_df = country_filtered_df[country_filtered_df["provider"].isin(selected_services)]
    all_sources = sorted(
        {s.strip() for val in source_filtered_df["source"].dropna() for s in str(val).split(",")}
    )

    if "all_sources" not in st.session_state:
        st.session_state["all_sources"] = False
        for s in all_sources:
            st.session_state[f"source_{s}"] = s != "Alyssa"

    with st.sidebar.popover("📋 Sources", use_container_width=True):
        st.checkbox(
            "Select all", key="all_sources",
            on_change=toggle_all, args=("source", all_sources, "all_sources")
        )
        for s in all_sources:
            st.checkbox(s, key=f"source_{s}")

    selected_sources = [s for s in all_sources if st.session_state.get(f"source_{s}", True)]
    if not selected_sources:
        selected_sources = all_sources

# --- ⚡ Actions ---
st.sidebar.markdown("---")
if "last_updated" in df.columns:
    last_date = df["last_updated"].max()
    st.sidebar.caption(f"📅 Data last updated: {last_date}")

st.sidebar.link_button(
    "⚡ Trigger data refresh",
    "https://github.com/bucanero2010/letterboxd-justwatch-vpn/actions/workflows/scrape.yml",
    use_container_width=True,
)

# =========================
# 🔎 TAB 1: WATCHLIST
# =========================
with tab_watchlist:
    st.markdown("## 🍿 Watchlist Availability")
    st.caption("Where your watchlist is streaming worldwide")

    filtered_df = df[
        (df["country"].isin(selected_countries)) &
        (df["provider"].isin(selected_services))
    ]

    if selected_owned_services:
        patterns = []
        for label in selected_owned_services:
            patterns.extend(OWNED_SERVICES_MAP[label])
        mask = pd.Series(False, index=filtered_df.index)
        for pattern in patterns:
            mask = mask | filtered_df["provider"].str.contains(pattern, regex=False)
        filtered_df = filtered_df[mask]

    if has_source_column and selected_sources:
        all_selected = has_source_column and len(selected_sources) == len(all_sources)
        if not all_selected:
            source_mask = filtered_df["source"].fillna("").apply(
                lambda val: any(s in val for s in selected_sources)
            )
            filtered_df = filtered_df[source_mask]

    if has_source_column:
        filtered_df = filtered_df.drop_duplicates(subset=["title", "year", "country", "provider"], keep="first")

    movies = filtered_df.groupby(["title", "year"]).agg({
        "country": list,
        "provider": list,
        "poster_url": "first",
        "runtime": "first"
    }).reset_index()

    # Active filter tags
    filter_tags = []
    if len(selected_countries) < len(countries):
        for c in selected_countries:
            filter_tags.append(f"{country_to_flag(c)} {c}")
    for label in selected_owned_services:
        filter_tags.append(f"🏠 {label}")
    if has_source_column and selected_sources and len(selected_sources) < len(all_sources):
        for s in selected_sources:
            filter_tags.append(f"📋 {s}")
    if filter_tags:
        tags_html = "".join(f'<span class="filter-tag">{t}</span>' for t in filter_tags)
        st.markdown(f'<div class="filter-tags">{tags_html}</div>', unsafe_allow_html=True)

    search_query = st.text_input("Search", placeholder="🔍 Search movie titles...", key="watchlist_search", label_visibility="collapsed")
    if search_query:
        movies = movies[movies["title"].str.contains(search_query, case=False, na=False)]

    sort_col1, sort_col2 = st.columns([3, 1])
    with sort_col2:
        sort_option = st.selectbox("Sort by", ["Runtime ↑", "Runtime ↓", "Title A-Z", "Year ↓", "Year ↑"], label_visibility="collapsed")

    if sort_option == "Runtime ↑":
        movies = movies.sort_values("runtime", na_position="last")
    elif sort_option == "Runtime ↓":
        movies = movies.sort_values("runtime", ascending=False, na_position="last")
    elif sort_option == "Title A-Z":
        movies = movies.sort_values("title")
    elif sort_option == "Year ↓":
        movies = movies.sort_values("year", ascending=False)
    elif sort_option == "Year ↑":
        movies = movies.sort_values("year")

    unique_countries = set()
    unique_providers = set()
    for _, m in movies.iterrows():
        unique_countries.update(m["country"])
        unique_providers.update(m["provider"])

    st.markdown(f"""
    <div class="stats-bar">
        <div class="stat-item">
            <div class="stat-value">{len(movies)}</div>
            <div class="stat-label">Movies</div>
        </div>
        <div class="stat-item">
            <div class="stat-value">{len(unique_countries)}</div>
            <div class="stat-label">Countries</div>
        </div>
        <div class="stat-item">
            <div class="stat-value">{len(unique_providers)}</div>
            <div class="stat-label">Providers</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    if movies.empty:
        st.info("😕 No movies match your filters.")
    else:
        n_cols = 5
        for i in range(0, len(movies), n_cols):
            cols = st.columns(n_cols, gap="medium")
            for j, col in enumerate(cols):
                if i + j < len(movies):
                    movie = movies.iloc[i + j]
                    with col:
                        st.image(movie["poster_url"], use_container_width=True)
                        runtime_text = format_runtime(movie.get("runtime"))
                        year_text = int(movie["year"])
                        st.markdown(f'<div class="movie-title">{movie["title"]}</div>', unsafe_allow_html=True)
                        st.markdown(f'<div class="movie-meta">{year_text} · {runtime_text}</div>', unsafe_allow_html=True)

                        country_providers: dict[str, list[str]] = {}
                        for c, p in zip(movie["country"], movie["provider"]):
                            country_providers.setdefault(c, []).append(p)

                        n_places = sum(len(v) for v in country_providers.values())
                        with st.expander(f"📍 {len(country_providers)} countries · {n_places} offers"):
                            for country in sorted(country_providers.keys()):
                                flag = country_to_flag(country)
                                st.markdown(f'<div class="country-header">{flag} {country}</div>', unsafe_allow_html=True)
                                badges = "".join(
                                    f'<span class="provider-badge">{p}</span>'
                                    for p in sorted(set(country_providers[country]))
                                )
                                st.markdown(badges, unsafe_allow_html=True)


# =========================
# 🔍 TAB 2: QUICK LOOKUP
# =========================
with tab_lookup:
    st.markdown("## 🔍 Quick Lookup")
    st.caption("Search any movie and see where it's streaming right now")

    lookup_col1, lookup_col2 = st.columns([3, 1])
    with lookup_col1:
        lookup_query = st.text_input("Movie name", placeholder="Type a movie name...", key="lookup_input", label_visibility="collapsed")
    with lookup_col2:
        lookup_year = st.number_input("Year (optional)", min_value=1900, max_value=2030, value=None, key="lookup_year")

    if lookup_query:
        with st.spinner("Searching JustWatch..."):
            try:
                from simplejustwatchapi import search as jw_search, offers_for_countries as jw_offers
                import json

                # Load countries from config
                config_path = BASE_DIR / "src" / "config.json"
                if config_path.exists():
                    with open(config_path) as f:
                        config = json.load(f)
                    lookup_countries = config.get("country_scan", ["US"])
                else:
                    lookup_countries = ["US"]

                # Search
                results = jw_search(lookup_query, country="US", language="en", count=5)

                # Filter by year if provided
                movie_results = [r for r in results if r.object_type == "MOVIE"]
                if lookup_year:
                    year_filtered = [r for r in movie_results if r.release_year and abs(r.release_year - lookup_year) <= 1]
                    if year_filtered:
                        movie_results = year_filtered

                if not movie_results:
                    st.warning("No movies found. Try a different search term.")
                else:
                    match = movie_results[0]
                    st.markdown(f"### {match.title} ({match.release_year})")

                    # Get offers
                    offers = jw_offers(match.entry_id, [c.upper() for c in lookup_countries])

                    has_offers = False
                    for country_code, country_offers in sorted(offers.items()):
                        streaming = [o for o in country_offers if o.monetization_type in ('FLATRATE', 'FREE', 'ADS')]
                        if streaming:
                            has_offers = True
                            flag = country_to_flag(country_code)
                            st.markdown(f'<div class="country-header">{flag} {country_code}</div>', unsafe_allow_html=True)
                            providers = sorted({o.package.name for o in streaming})
                            badges = "".join(f'<span class="provider-badge">{p}</span>' for p in providers)
                            st.markdown(badges, unsafe_allow_html=True)

                    if not has_offers:
                        st.info("😕 No streaming offers found in your countries.")

            except Exception as e:
                st.error(f"Lookup failed: {e}")

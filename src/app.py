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
tab_watchlist, tab_lookup, tab_recommend = st.tabs(["🍿 Watchlist", "🔍 Quick Lookup", "🎯 Recommendations"])

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


# =========================
# 🎯 TAB 3: RECOMMENDATIONS
# =========================
with tab_recommend:
    import json as _json
    from recommender import HybridRecommender, RecommendationResult
    from letterbox_scraper import scrape_films, scrape_ratings
    from justwatch_query import get_film_offers_api

    st.markdown("## 🎯 Recommendations")
    st.caption("Personalized movie recommendations powered by your watch history")

    # Load config
    _config_path = BASE_DIR / "src" / "config.json"
    if _config_path.exists():
        with open(_config_path) as _f:
            _config = _json.load(_f)
    else:
        _config = {}

    _data_dir = BASE_DIR / "data"
    _username = _config.get("letterboxd_user", "")
    _countries = _config.get("country_scan", ["US"])

    if not _username:
        st.warning("⚠️ No Letterboxd username configured in `src/config.json`.")
        st.stop()

    # Initialize recommender
    _recommender = HybridRecommender(config=_config, data_dir=_data_dir)

    # Initialize session state for recommendations
    if "rec_results" not in st.session_state:
        st.session_state["rec_results"] = None
    if "rec_page" not in st.session_state:
        st.session_state["rec_page"] = 1
    if "rec_streaming_filter" not in st.session_state:
        st.session_state["rec_streaming_filter"] = False
    if "rec_streaming_cache" not in st.session_state:
        st.session_state["rec_streaming_cache"] = {}

    RECS_PER_PAGE = 20

    # --- Status Panel ---
    _results_path = _data_dir / "recommendations.json"
    _model_exists = (_data_dir / "lightfm_model.pkl").exists()
    _metadata_cached = (_data_dir / "tmdb_metadata_cache.json").exists()
    _embeddings_cached = (_data_dir / "plot_embeddings.npz").exists()
    _watch_cache_exists = (_data_dir / "watch_history_cache.json").exists()
    _unmapped_path = _data_dir / "unmapped_films.json"
    _n_unmapped = 0
    if _unmapped_path.exists():
        try:
            _n_unmapped = len(_json.load(open(_unmapped_path)))
        except Exception:
            pass

    with st.expander("📊 System Status", expanded=not _model_exists):
        _col_s1, _col_s2, _col_s3 = st.columns(3)
        with _col_s1:
            if _model_exists:
                import datetime
                _model_age = (datetime.datetime.now().timestamp() - (_data_dir / "lightfm_model.pkl").stat().st_mtime) / 3600
                st.metric("Model", f"✅ {_model_age:.0f}h old")
            else:
                st.metric("Model", "❌ Not trained")
        with _col_s2:
            if _metadata_cached:
                _n_meta = len(_json.load(open(_data_dir / "tmdb_metadata_cache.json"))) if _metadata_cached else 0
                st.metric("Metadata", f"✅ {_n_meta:,} movies")
            else:
                st.metric("Metadata", "❌ Not cached")
        with _col_s3:
            st.metric("Unmapped", f"⚠️ {_n_unmapped} films" if _n_unmapped else "✅ All mapped")

    # --- Action Buttons ---
    st.markdown("**Actions:**")
    _btn_col1, _btn_col2, _btn_col3 = st.columns(3)

    with _btn_col1:
        _quick_update = st.button(
            "⚡ Quick Update",
            help="Incremental update — adjusts model for new ratings (seconds). Use when you've watched/rated a few new movies.",
            use_container_width=True,
            disabled=not _model_exists,
        )
    with _btn_col2:
        _full_retrain = st.button(
            "🏗️ Full Retrain",
            help="Rebuilds everything from scratch including new movies not in the dataset (~10 min). Use for first run or major changes.",
            use_container_width=True,
        )
    with _btn_col3:
        _expand_dataset = st.button(
            "📥 Expand & Retrain",
            help=f"Adds {_n_unmapped} missing movies to the training matrix and retrains. Use to include recent films.",
            use_container_width=True,
            disabled=_n_unmapped == 0,
        )

    # Determine which action to take
    retrain_clicked = _full_retrain
    _expand_clicked = _expand_dataset
    _incremental_clicked = _quick_update

    # Check if model is fresh and we have cached results
    _model_is_fresh = _recommender.is_model_fresh()

    # Determine if we need to generate recommendations
    _need_generation = False

    if retrain_clicked or _incremental_clicked or _expand_clicked:
        _need_generation = True
        st.session_state["rec_results"] = None
        st.session_state["rec_page"] = 1
        st.session_state["rec_streaming_cache"] = {}

    if st.session_state["rec_results"] is None:
        # If model exists, always run recommend() fresh (ensures exclusion logic is current)
        if _model_exists:
            try:
                _recommender._load_cached_model()
                st.session_state["rec_results"] = _recommender.recommend(n=50)
                _recommender.serialize_results(st.session_state["rec_results"], _results_path)
            except Exception as _e:
                logger.warning(f"Failed to generate recommendations from cached model: {_e}")
                _need_generation = True
        else:
            _need_generation = True

    # Show generate button or run generation
    if _need_generation and not retrain_clicked and not _incremental_clicked and not _expand_clicked:
        st.info(
            "🎬 No recommendations available yet. Use one of the action buttons above to generate "
            "personalized recommendations based on your Letterboxd watch history."
        )

    if _incremental_clicked and _model_exists:
        _progress_placeholder = st.empty()
        _log_placeholder = st.empty()
        _log_messages = []

        def _inc_progress_cb(msg):
            import datetime
            timestamp = datetime.datetime.now().strftime("%H:%M:%S")
            _log_messages.append(f"[{timestamp}] {msg}")
            _progress_placeholder.info(f"⚡ {msg}")
            _log_placeholder.code("\n".join(_log_messages[-10:]), language=None)

        with st.spinner("Quick update..."):
            _watch_history_cache = _data_dir / "watch_history_cache.json"
            if _watch_history_cache.exists():
                _watch_history = _json.load(open(_watch_history_cache))
            else:
                _watch_history = []

            if _watch_history:
                _recommender.train(_watch_history, progress_callback=_inc_progress_cb)
                _recs = _recommender.recommend(n=50)
                _recommender.serialize_results(_recs, _results_path)
                st.session_state["rec_results"] = _recs
                _progress_placeholder.success(f"⚡ Quick update complete! {len(_recs)} recommendations.")
            else:
                st.warning("No cached watch history. Use Full Retrain instead.")
    if retrain_clicked:
        _progress_placeholder = st.empty()
        _progress_bar = st.progress(0)
        _log_placeholder = st.empty()
        _log_messages = []

        def _progress_cb(msg):
            import datetime
            timestamp = datetime.datetime.now().strftime("%H:%M:%S")
            _log_messages.append(f"[{timestamp}] {msg}")
            _progress_placeholder.info(f"🔄 {msg}")
            # Show last 15 log entries
            _log_placeholder.code("\n".join(_log_messages[-15:]), language=None)

        with st.spinner("Training recommendation model... This may take a few minutes on first run."):
            _progress_cb("Scraping watch history from Letterboxd...")
            _progress_bar.progress(5)

            # Try to load cached watch history first, scrape only if missing
            _watch_history_cache = _data_dir / "watch_history_cache.json"
            _watch_history = None

            if _watch_history_cache.exists() and not retrain_clicked:
                try:
                    with open(_watch_history_cache, "r") as _f:
                        _watch_history = _json.load(_f)
                    _progress_cb(f"Loaded {len(_watch_history)} films from cache")
                except Exception:
                    _watch_history = None

            if not _watch_history:
                # Scrape the user's FULL watch history with ratings using Playwright
                from playwright.sync_api import sync_playwright
                _watch_history_url = f"https://letterboxd.com/{_username}/films/ratings/"
                try:
                    with sync_playwright() as _pw:
                        _browser = _pw.chromium.launch(headless=True, channel="chromium")
                        _ctx = _browser.new_context(user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
                        _ctx.add_init_script('Object.defineProperty(navigator, "webdriver", {get: () => undefined})')
                        _pw_page = _ctx.new_page()
                        _watch_history = scrape_ratings(_watch_history_url, pw_page=_pw_page, max_pages=100)
                        _browser.close()
                except Exception as _e:
                    st.error(f"❌ Failed to launch browser: {_e}")
                    st.stop()

                # Cache the watch history for next time
                if _watch_history:
                    with open(_watch_history_cache, "w") as _f:
                        _json.dump(_watch_history, _f)

            if not _watch_history:
                st.error("❌ No Letterboxd watch history found. Make sure your profile is public.")
                st.stop()

            _progress_bar.progress(15)
            _progress_cb(f"Found {len(_watch_history)} watched films. Training model...")

            try:
                _recommender.retrain(
                    watch_history=_watch_history,
                    progress_callback=_progress_cb,
                )
                _progress_bar.progress(85)
                _progress_cb("Generating recommendations...")

                _recs = _recommender.recommend(n=50)
                _recommender.serialize_results(_recs, _results_path)
                st.session_state["rec_results"] = _recs
                st.session_state["rec_page"] = 1
                st.session_state["rec_streaming_cache"] = {}

                _progress_bar.progress(100)
                _progress_placeholder.success(f"✅ Generated {len(_recs)} recommendations!")

            except Exception as e:
                _progress_bar.empty()
                _progress_placeholder.empty()
                st.error(f"❌ Recommendation generation failed: {e}")
                st.stop()

    if _expand_clicked:
        _progress_placeholder = st.empty()
        _progress_bar = st.progress(0)
        _log_placeholder = st.empty()
        _log_messages = []

        def _progress_cb(msg):
            import datetime
            timestamp = datetime.datetime.now().strftime("%H:%M:%S")
            _log_messages.append(f"[{timestamp}] {msg}")
            _progress_placeholder.info(f"📥 {msg}")
            _log_placeholder.code("\n".join(_log_messages[-15:]), language=None)

        with st.spinner("Expanding dataset and retraining... This may take several minutes."):
            _progress_cb("Loading watch history...")
            _progress_bar.progress(5)

            _watch_history_cache = _data_dir / "watch_history_cache.json"
            if _watch_history_cache.exists():
                _watch_history = _json.load(open(_watch_history_cache))
            else:
                _watch_history = []

            if not _watch_history:
                st.warning("No cached watch history. Use Full Retrain instead.")
                st.stop()

            _progress_bar.progress(10)

            try:
                _recommender.expand_and_retrain(
                    watch_history=_watch_history,
                    progress_callback=_progress_cb,
                )
                _progress_bar.progress(85)
                _progress_cb("Generating recommendations...")

                _recs = _recommender.recommend(n=50)
                _recommender.serialize_results(_recs, _results_path)
                st.session_state["rec_results"] = _recs
                st.session_state["rec_page"] = 1
                st.session_state["rec_streaming_cache"] = {}

                _progress_bar.progress(100)
                _progress_placeholder.success(
                    f"✅ Expand & Retrain complete! {len(_recs)} recommendations generated."
                )

            except Exception as e:
                _progress_bar.empty()
                _progress_placeholder.empty()
                st.error(f"❌ Expand & Retrain failed: {e}")
                st.stop()

    # --- Display Recommendations ---
    _recs_to_display = st.session_state.get("rec_results")

    # Show unmapped films if available
    _unmapped_path = _data_dir / "unmapped_films.json"
    if _unmapped_path.exists():
        try:
            with open(_unmapped_path, "r") as _f:
                _unmapped = _json.load(_f)
            if _unmapped:
                with st.expander(f"⚠️ {len(_unmapped)} watched films not included in training (not in MovieLens)"):
                    for film in _unmapped:
                        st.caption(film)
        except Exception:
            pass

    if _recs_to_display:
        # Load TMDB metadata for enriching cards
        _tmdb_meta_path = _data_dir / "tmdb_metadata_cache.json"
        _tmdb_meta = {}
        if _tmdb_meta_path.exists():
            try:
                with open(_tmdb_meta_path, "r") as _f:
                    _tmdb_meta_raw = _json.load(_f)
                _tmdb_meta = {int(k): v for k, v in _tmdb_meta_raw.items()}
            except Exception:
                pass

        # Streaming filter toggle
        st.checkbox(
            "📺 Filter by my streaming services",
            key="rec_streaming_filter",
            help="Show only movies available on your owned streaming services",
        )

        _filtered_recs = _recs_to_display

        # Apply streaming filter if enabled
        if st.session_state["rec_streaming_filter"] and selected_owned_services:
            _owned_provider_names = []
            for label in selected_owned_services:
                _owned_provider_names.extend(OWNED_SERVICES_MAP[label])

            _streaming_filtered = []
            _cache = st.session_state["rec_streaming_cache"]

            with st.spinner("Checking streaming availability..."):
                for rec in _recs_to_display:
                    _cache_key = rec.tmdb_id
                    if _cache_key not in _cache:
                        # Query JustWatch for this movie
                        offers = get_film_offers_api(
                            title=rec.title,
                            year=rec.year,
                            countries=_countries,
                        )
                        _cache[_cache_key] = offers
                    else:
                        offers = _cache[_cache_key]

                    # Check if any offer matches owned services
                    if offers:
                        all_providers = set()
                        for providers_list in offers.values():
                            all_providers.update(providers_list)
                        if any(
                            owned_p.lower() in p.lower()
                            for p in all_providers
                            for owned_p in _owned_provider_names
                        ):
                            _streaming_filtered.append(rec)

            st.session_state["rec_streaming_cache"] = _cache
            _filtered_recs = _streaming_filtered

        # Stats bar
        _current_page = st.session_state["rec_page"]
        _total_recs = len(_filtered_recs)
        _display_count = min(_current_page * RECS_PER_PAGE, _total_recs)

        st.markdown(f"""
        <div class="stats-bar">
            <div class="stat-item">
                <div class="stat-value">{_total_recs}</div>
                <div class="stat-label">Recommendations</div>
            </div>
            <div class="stat-item">
                <div class="stat-value">{_display_count}</div>
                <div class="stat-label">Showing</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        if not _filtered_recs:
            st.info("😕 No recommendations match your streaming filter. Try disabling the filter or adding more services.")
        else:
            # Display paginated results in grid
            _page_recs = _filtered_recs[:_display_count]
            n_cols = 5

            for i in range(0, len(_page_recs), n_cols):
                cols = st.columns(n_cols, gap="medium")
                for j, col in enumerate(cols):
                    if i + j < len(_page_recs):
                        rec = _page_recs[i + j]
                        with col:
                            # Poster
                            if rec.poster_url:
                                st.image(rec.poster_url, use_container_width=True)
                            else:
                                st.markdown("🎬", unsafe_allow_html=True)

                            # Title and metadata
                            st.markdown(f'<div class="movie-title">{rec.title}</div>', unsafe_allow_html=True)
                            runtime_text = format_runtime(rec.runtime)
                            year_text = rec.year if rec.year else "—"
                            st.markdown(f'<div class="movie-meta">{year_text} · {runtime_text}</div>', unsafe_allow_html=True)

                            # Score as percentage bar
                            score_pct = int(rec.score * 100)
                            st.progress(rec.score, text=f"Match: {score_pct}%")

                            # Genre badges
                            if rec.genres:
                                genre_badges = "".join(
                                    f'<span class="provider-badge">{g}</span>'
                                    for g in rec.genres[:3]
                                )
                                st.markdown(genre_badges, unsafe_allow_html=True)

                            # Director, cast, and plot from metadata
                            _meta = _tmdb_meta.get(rec.tmdb_id, {})
                            _directors = _meta.get("directors", [])
                            _cast = _meta.get("cast", [])
                            _overview = _meta.get("overview", "")

                            _info_parts = []
                            if _directors:
                                _info_parts.append(f"🎬 {', '.join(_directors[:2])}")
                            if _cast:
                                _info_parts.append(f"🎭 {', '.join(_cast[:3])}")
                            if _info_parts:
                                st.caption(" · ".join(_info_parts))
                            if _overview:
                                # Show first ~100 chars of plot
                                _short_plot = _overview[:120] + "..." if len(_overview) > 120 else _overview
                                st.caption(_short_plot)

                            # Streaming availability (from cache if available)
                            _cache = st.session_state["rec_streaming_cache"]
                            if rec.tmdb_id in _cache and _cache[rec.tmdb_id]:
                                offers = _cache[rec.tmdb_id]
                                n_countries_with_offers = len(offers)
                                n_total_offers = sum(len(v) for v in offers.values())
                                with st.expander(f"📍 {n_countries_with_offers} countries · {n_total_offers} offers"):
                                    for country_code in sorted(offers.keys()):
                                        flag = country_to_flag(country_code)
                                        st.markdown(f'<div class="country-header">{flag} {country_code}</div>', unsafe_allow_html=True)
                                        badges = "".join(
                                            f'<span class="provider-badge">{p}</span>'
                                            for p in sorted(offers[country_code])
                                        )
                                        st.markdown(badges, unsafe_allow_html=True)

            # Load more button
            if _display_count < _total_recs:
                if st.button(f"📥 Load more ({_total_recs - _display_count} remaining)", key="load_more_btn", use_container_width=True):
                    st.session_state["rec_page"] += 1
                    st.rerun()

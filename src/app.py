import streamlit as st
import pandas as pd
from pathlib import Path

st.set_page_config(
    page_title="Global Watchlist",
    layout="wide",
    page_icon="🍿"
)

# =========================
# 🍿 HEADER
# =========================
st.markdown("## 🍿 Watchlist Availability")
st.markdown("**Where your watchlist is streaming worldwide**")

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
    
    # FIX: The UK flag is tied to the GB ISO code
    if code == "UK":
        code = "GB"
        
    if len(code) != 2:
        return code
        
    # Standard Regional Indicator Symbol formula
    # Offset 127397 is sometimes used, but 127462 - ord('A') is safer
    return "".join(chr(ord(c) + 127397) for c in code)

def format_runtime(runtime):
    return f"⏱️ {runtime} min" if pd.notna(runtime) else ""

# =========================
# 🎛️ SIDEBAR FILTERS
# =========================
st.sidebar.markdown("## Filters")

# --- 🌍 Countries (popover with checkboxes) ---
countries = sorted(df["country"].unique().tolist())

with st.sidebar.popover("🌍 Countries", use_container_width=True):
    all_countries_checked = st.checkbox("Select all", value=True, key="all_countries")
    country_selections = {}
    for c in countries:
        label = f"{country_to_flag(c)} {c}"
        country_selections[c] = st.checkbox(label, value=all_countries_checked, key=f"country_{c}")

selected_countries = [c for c, checked in country_selections.items() if checked]
if not selected_countries:
    selected_countries = countries  # fallback to all if none selected

# --- 📺 Services (cascaded from country, popover with checkboxes) ---
country_filtered_df = df[df["country"].isin(selected_countries)]
services = sorted(country_filtered_df["provider"].unique().tolist())

with st.sidebar.popover("📺 Streaming services", use_container_width=True):
    all_services_checked = st.checkbox("Select all", value=True, key="all_services")
    service_selections = {}
    for s in services:
        service_selections[s] = st.checkbox(s, value=all_services_checked, key=f"service_{s}")

selected_services = [s for s, checked in service_selections.items() if checked]
if not selected_services:
    selected_services = services  # fallback to all if none selected

# --- 📋 Sources (cascaded, only if column exists) ---
has_source_column = "source" in df.columns
selected_source = "📋 All sources"

if has_source_column:
    source_filtered_df = country_filtered_df[country_filtered_df["provider"].isin(selected_services)]
    all_sources = sorted(
        {s.strip() for val in source_filtered_df["source"].dropna() for s in str(val).split(",")}
    )
    source_options = ["📋 All sources"] + all_sources
    selected_source = st.sidebar.selectbox(
        "📋 Source",
        options=source_options,
        index=0
    )

# =========================
# 🔎 FILTERING
# =========================
filtered_df = df[
    (df["country"].isin(selected_countries)) &
    (df["provider"].isin(selected_services))
]

# Apply source filter
if has_source_column and selected_source != "📋 All sources":
    filtered_df = filtered_df[
        filtered_df["source"].fillna("").str.contains(selected_source, regex=False)
    ]

# Deduplicate by (title, year) when showing all sources
if has_source_column and selected_source == "📋 All sources":
    filtered_df = filtered_df.drop_duplicates(subset=["title", "year", "country", "provider"], keep="first")

# =========================
# 🎬 GRID DISPLAY
# =========================
# Group by movie to avoid duplicates
movies = filtered_df.groupby(["title", "year"]).agg({
    "country": list,
    "provider": list,
    "poster_url": "first",
    "runtime": "first"
}).reset_index()

# 🔍 Search above grid
search_query = st.text_input(
    "",
    placeholder="🔍 Search movie titles..."
)
if search_query:
    movies = movies[movies["title"].str.contains(search_query, case=False, na=False)]

# 🔢 SORTING by runtime ascending by default
movies = movies.sort_values("runtime", na_position="last")  # shortest → longest

if movies.empty:
    st.info("😕 No movies match your filters.")
else:
    n_cols = 5
    for i in range(0, len(movies), n_cols):
        cols = st.columns(n_cols)
        for j, col in enumerate(cols):
            if i + j < len(movies):
                movie = movies.iloc[i + j]
                with col:
                    st.image(movie["poster_url"], use_container_width=True)
                    runtime_text = format_runtime(movie.get("runtime"))
                    st.markdown(f"**{movie['title']}** ({int(movie['year'])}) {runtime_text}")

                    availability = sorted(
                        set(
                            f"{country_to_flag(c)} {c}: {p}"
                            for c, p in zip(movie["country"], movie["provider"])
                        )
                    )
                    with st.expander(f"📍 Available in {len(availability)} places"):
                        for item in availability:
                            st.caption(item)

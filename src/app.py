import streamlit as st
import pandas as pd
from pathlib import Path

st.set_page_config(
    page_title="Global Watchlist",
    layout="wide",
    page_icon="🍿"
)

# --- HEADER ---
st.title("🍿 Watchlist Availability")
st.caption("Where your watchlist is streaming around the world")

# --- PATHING ---
BASE_DIR = Path(__file__).resolve().parent.parent
file_path = BASE_DIR / "data" / "unwatched_by_country.csv"

if not file_path.exists():
    st.error("CSV file not found. Run your scraper first!")
    st.stop()

df = pd.read_csv(file_path)

# --- SIDEBAR FILTERS ---
st.sidebar.title("🎯 Filters")

# Country filter (with All)
countries = sorted(df["country"].unique().tolist())
country_options = ["All"] + countries
selected_country = st.sidebar.selectbox(
    "Country",
    options=country_options,
    index=0
)

# Service filter (multi-select with All)
services = sorted(df["provider"].unique().tolist())
service_options = ["All"] + services
selected_services = st.sidebar.multiselect(
    "Streaming services",
    options=service_options,
    default=["All"]
)

# Sorting
sort_option = st.sidebar.selectbox(
    "Sort by",
    ["Title (A–Z)", "Most availability", "Year (newest)"]
)

# --- SEARCH ---
search_query = st.text_input(
    "",
    placeholder="🔍 Search movie titles..."
)

# --- FILTERING ---
filtered_df = df.copy()

if selected_country != "All":
    filtered_df = filtered_df[filtered_df["country"] == selected_country]

if "All" not in selected_services:
    filtered_df = filtered_df[filtered_df["provider"].isin(selected_services)]

if search_query:
    filtered_df = filtered_df[
        filtered_df["title"].str.contains(search_query, case=False, na=False)
    ]

# --- GROUP MOVIES ---
movies = (
    filtered_df
    .groupby(["title", "year"], as_index=False)
    .agg({
        "country": list,
        "provider": list,
        "poster_url": "first"
    })
)

# --- SORTING ---
if sort_option == "Title (A–Z)":
    movies = movies.sort_values("title")
elif sort_option == "Most availability":
    movies["availability_count"] = movies["country"].apply(len)
    movies = movies.sort_values("availability_count", ascending=False)
elif sort_option == "Year (newest)":
    movies = movies.sort_values("year", ascending=False)

# --- DISPLAY ---
if movies.empty:
    st.info("🎬 No movies match your filters. Try widening your search.")
else:
    n_cols = 5
    for i in range(0, len(movies), n_cols):
        cols = st.columns(n_cols)
        for j, col in enumerate(cols):
            if i + j >= len(movies):
                continue

            movie = movies.iloc[i + j]

            with col:
                with st.container(border=True):
                    st.image(movie["poster_url"], use_container_width=True)

                    st.markdown(
                        f"### {movie['title']}\n"
                        f"<span style='color:gray'>({int(movie['year'])})</span>",
                        unsafe_allow_html=True
                    )

                    availability = sorted(
                        set(f"{c}: {p}" for c, p in zip(movie["country"], movie["provider"]))
                    )

                    countries_count = len(set(movie["country"]))
                    services_count = len(set(movie["provider"]))

                    with st.expander(
                        f"📍 {countries_count} countries · {services_count} services"
                    ):
                        for item in availability:
                            st.caption(item)

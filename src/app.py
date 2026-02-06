import streamlit as st
import pandas as pd
from pathlib import Path

st.set_page_config(
    page_title="🍿 Global Watchlist",
    layout="wide",
    page_icon="🍿"
)

# =========================
# 🍿 HEADER
# =========================
st.markdown("## 🍿 Global Watchlist")
st.markdown("🌍 **Where your watchlist is streaming worldwide**")

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
    if len(code) != 2:
        return code
    return "".join(chr(127397 + ord(c)) for c in code.upper())

# =========================
# 🎛️ SIDEBAR FILTERS
# =========================
st.sidebar.markdown("## 🎛️ Filters")

# 🌍 Countries with flags
countries = sorted(df["country"].unique().tolist())
country_labels = {c: f"{country_to_flag(c)} {c}" for c in countries}

country_options = ["🌍 All countries"] + list(country_labels.values())
selected_country_labels = st.sidebar.multiselect(
    "🌍 Countries",
    options=country_options,
    default=["🌍 All countries"]
)

if "🌍 All countries" in selected_country_labels:
    selected_countries = countries
else:
    selected_countries = [
        c for c, label in country_labels.items()
        if label in selected_country_labels
    ]

# 📺 Services
services = sorted(df["provider"].unique().tolist())
service_options = ["📺 All services"] + services
selected_services = st.sidebar.multiselect(
    "📺 Streaming services",
    options=service_options,
    default=["📺 All services"]
)

if "📺 All services" in selected_services:
    selected_services = services

# 🔍 Search
search_query = st.text_input(
    "",
    placeholder="🔍 Search movie titles..."
)

# =========================
# 🔎 FILTERING
# =========================
filtered_df = df[
    (df["country"].isin(selected_countries)) &
    (df["provider"].isin(selected_services))
]

if search_query:
    filtered_df = filtered_df[
        filtered_df["title"].str.contains(search_query, case=False, na=False)
    ]

# =========================
# 🎬 GRID DISPLAY
# =========================
movies = filtered_df.groupby(["title", "year"]).agg({
    "country": list,
    "provider": list,
    "poster_url": "first"
}).reset_index()

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
                    st.markdown(f"**{movie['title']}** ({int(movie['year'])})")

                    availability = sorted(
                        set(
                            f"{country_to_flag(c)} {c}: {p}"
                            for c, p in zip(movie["country"], movie["provider"])
                        )
                    )

                    with st.expander(f"📍 Available in {len(availability)} places"):
                        for item in availability:
                            st.caption(item)

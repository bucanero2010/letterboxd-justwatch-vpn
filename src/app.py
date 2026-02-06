import streamlit as st
import pandas as pd
from pathlib import Path

# --- PAGE CONFIG ---
st.set_page_config(page_title="Global Watchlist", layout="wide", page_icon="🍿")

# --- CUSTOM CSS FOR POSTERS ---
st.markdown("""
    <style>
    .stImage > img {
        border-radius: 10px;
        transition: transform .3s;
        box-shadow: 0 4px 8px rgba(0,0,0,0.2);
    }
    .stImage > img:hover {
        transform: scale(1.03);
        box-shadow: 0 8px 16px rgba(0,0,0,0.4);
    }
    </style>
""", unsafe_allow_html=True)

# --- PATHING ---
BASE_DIR = Path(__file__).resolve().parent.parent 
file_path = BASE_DIR / "data" / "unwatched_by_country.csv"

if file_path.exists():
    df = pd.read_csv(file_path)
    
    # --- SIDEBAR FILTERS ---
    st.sidebar.title("🎯 Filters")
    
    all_countries = sorted(df['country'].unique())
    selected_country = st.sidebar.multiselect("Select Countries", all_countries, default=all_countries)
    
    all_services = sorted(df['provider'].unique())
    selected_service = st.sidebar.multiselect("Select Services", all_services, default=all_services)

    # --- SEARCH BAR ---
    search_query = st.text_input("", placeholder="🔍 Search your watchlist (e.g., 'Inception' or '2010')...")

    # --- FILTERING LOGIC ---
    filtered_df = df[
        (df['country'].isin(selected_country)) & 
        (df['provider'].isin(selected_service))
    ]
    
    if search_query:
        filtered_df = filtered_df[filtered_df['title'].str.contains(search_query, case=False, na=False)]

    # --- GRID DISPLAY ---
    # Grouping by title so we show one poster with multiple flags/providers
    movies = filtered_df.groupby(['title', 'year']).agg({
        'country': list,
        'provider': list,
        # Fallback if poster_url doesn't exist yet
        'poster_url': 'first' if 'poster_url' in df.columns else lambda x: "https://via.placeholder.com/500x750?text=No+Poster"
    }).reset_index()

    if movies.empty:
        st.warning("No movies found with those filters!")
    else:
        # Create columns (responsive-ish grid)
        n_cols = 5
        rows = [movies[i:i + n_cols] for i in range(0, movies.shape[0], n_cols)]

        for row in rows:
            cols = st.columns(n_cols)
            for i, (_, movie) in enumerate(row.iterrows()):
                with cols[i]:
                    # Poster Image
                    st.image(movie['poster_url'], use_container_width=True)
                    
                    # Title & Year
                    st.markdown(f"**{movie['title']}** ({int(movie['year'])})")
                    
                    # Displaying unique availability
                    # Combining country + provider for a clean list
                    availability = list(set([f"{c}: {p}" for c, p in zip(movie['country'], movie['provider'])]))
                    for item in availability[:3]: # Show top 3 to keep it clean
                        st.caption(f"📍 {item}")
                    if len(availability) > 3:
                        st.caption(f" + {len(availability)-3} more options")

else:
    st.title("🍿 Global Watchlist")
    st.error("Data file not found. Please run the scraper first!")
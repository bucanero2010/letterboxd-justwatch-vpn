import streamlit as st
import pandas as pd
from pathlib import Path

st.set_page_config(page_title="Global Watchlist", layout="wide", page_icon="🍿")

# Add this near your st.set_page_config
st.markdown("""
    <style>
    /* Hide the Streamlit header and footer for a cleaner mobile look */
    header {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* Make the app take up the full screen height on mobile */
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
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
    
    # Country Filter with Select All
    all_countries = sorted(df['country'].unique().tolist())
    select_all_countries = st.sidebar.checkbox("Select all countries", value=True)
    if select_all_countries:
        selected_countries = st.sidebar.multiselect("Countries", all_countries, default=all_countries)
    else:
        selected_countries = st.sidebar.multiselect("Countries", all_countries)

    # Service Filter with Select All
    all_services = sorted(df['provider'].unique().tolist())
    select_all_services = st.sidebar.checkbox("Select all services", value=True)
    if select_all_services:
        selected_services = st.sidebar.multiselect("Services", all_services, default=all_services)
    else:
        selected_services = st.sidebar.multiselect("Services", all_services)

    # --- SEARCH & FILTER ---
    search_query = st.text_input("", placeholder="🔍 Search movie titles...")

    filtered_df = df[
        (df['country'].isin(selected_countries)) & 
        (df['provider'].isin(selected_services))
    ]
    
    if search_query:
        filtered_df = filtered_df[filtered_df['title'].str.contains(search_query, case=False, na=False)]

    # --- GRID DISPLAY ---
    # Group by movie to avoid duplicates
    movies = filtered_df.groupby(['title', 'year']).agg({
        'country': list,
        'provider': list,
        'poster_url': 'first'
    }).reset_index()

    if movies.empty:
        st.info("No movies match your filters.")
    else:
        # Create a clean grid
        n_cols = 5
        for i in range(0, len(movies), n_cols):
            cols = st.columns(n_cols)
            for j, col in enumerate(cols):
                if i + j < len(movies):
                    movie = movies.iloc[i + j]
                    with col:
                        # Display Poster
                        st.image(movie['poster_url'], use_container_width=True)
                        st.markdown(f"**{movie['title']}** ({int(movie['year'])})")
                        
                        # CLEAN UI SOLUTION: The Expander
                        # Combine country and provider into unique strings
                        availability = sorted(list(set([f"{c}: {p}" for c, p in zip(movie['country'], movie['provider'])])))
                        
                        with st.expander(f"📍 Available on {len(availability)} options"):
                            for item in availability:
                                st.caption(item)
else:
    st.error("CSV file not found. Run your scraper first!")
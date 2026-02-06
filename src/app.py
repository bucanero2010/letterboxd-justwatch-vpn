import streamlit as st
import pandas as pd
import os
import datetime

st.set_page_config(page_title="Letterboxd Stream Finder", layout="wide", page_icon="🎬")

file_path = "data/unwatched_by_country.csv"

if os.path.exists(file_path):
    # Get the last updated time of the file
    last_updated_ts = os.path.getmtime(file_path)
    last_updated_dt = datetime.datetime.fromtimestamp(last_updated_ts)
    
    st.title("🎬 Global Stream Finder")
    st.caption(f"Last updated: {last_updated_dt.strftime('%Y-%m-%d %H:%M:%S')} UTC")

    df = pd.read_csv(file_path)

    # Search bar
    search_query = st.text_input("🔍 Search title:", placeholder="e.g., The Handmaiden")

    # Sidebar
    st.sidebar.header("Filters")
    countries = ["All"] + sorted(df['country'].unique().tolist())
    selected_country = st.sidebar.selectbox("Country:", countries)
    
    # Filter logic
    filtered_df = df.copy()
    if search_query:
        filtered_df = filtered_df[filtered_df['title'].str.contains(search_query, case=False, na=False)]
    if selected_country != "All":
        filtered_df = filtered_df[filtered_df['country'] == selected_country]

    st.dataframe(filtered_df[['title', 'year', 'country', 'provider']].reset_index(drop=True), width='stretch')

else:
    st.error("No data found. Wait for the first scraper run to finish!")
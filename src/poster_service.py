import requests

def get_poster_url(title, year, api_token):
    """Fetches movie poster from TMDB using a Bearer Token."""
    url = "https://api.themoviedb.org/3/search/movie"
    params = {
        "query": title, 
        "year": year, 
        "language": "en-US"
    }
    headers = {
        "accept": "application/json",
        "Authorization": f"Bearer {api_token}"
    }
    
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        
        if data.get('results'):
            poster_path = data['results'][0].get('poster_path')
            if poster_path:
                return f"https://image.tmdb.org/t/p/w500{poster_path}"
    except Exception as e:
        print(f"⚠️ TMDB Error for {title}: {e}")
    
    # Return a high-quality placeholder if search fails
    return "https://via.placeholder.com/500x750?text=No+Poster+Found"
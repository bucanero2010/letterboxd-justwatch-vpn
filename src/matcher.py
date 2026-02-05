def get_unwatched(watchlist, watched):
    watched_slugs = {f["slug"] for f in watched}

    unwatched = [
        f for f in watchlist
        if f["slug"] not in watched_slugs
    ]

    return unwatched

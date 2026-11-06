"""Vercel Python function: GET /api/lookup?q=<title>&year=<yyyy>&countries=ES,US,..."""

import json
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

from simplejustwatchapi import offers_for_countries, search

# Config country code -> JustWatch country code, where they differ
JUSTWATCH_COUNTRY = {"UK": "GB"}


class handler(BaseHTTPRequestHandler):
    def _send(self, status, body):
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "s-maxage=3600, stale-while-revalidate")
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        params = parse_qs(urlparse(self.path).query)
        query = (params.get("q") or [""])[0].strip()
        year = (params.get("year") or [""])[0]
        countries = [c.upper() for c in (params.get("countries") or ["US"])[0].split(",") if c]

        if not query:
            return self._send(400, {"error": "Missing q"})

        try:
            results = [r for r in search(query, country="US", language="en", count=5)
                       if r.object_type == "MOVIE"]
            if year.isdigit():
                near = [r for r in results if r.release_year and abs(r.release_year - int(year)) <= 1]
                results = near or results
            if not results:
                return self._send(200, {"error": "No movies found. Try a different search term."})

            # Prefer an exact title match; JustWatch's top hit can be a sequel or namesake.
            exact = [r for r in results if r.title.casefold() == query.casefold()]
            match = (exact or results)[0]

            # JustWatch uses ISO "GB"; the app uses "UK".
            to_jw = {c: JUSTWATCH_COUNTRY.get(c, c) for c in countries}
            from_jw = {v: k for k, v in to_jw.items()}
            offers = offers_for_countries(match.entry_id, set(to_jw.values()))
            out = {}
            for jw_country, country_offers in offers.items():
                country = from_jw.get(jw_country, jw_country)
                providers = sorted({o.package.name for o in country_offers
                                    if o.monetization_type in ("FLATRATE", "FREE", "ADS")})
                if providers:
                    out[country] = providers
            self._send(200, {"title": match.title, "year": match.release_year, "offers": out})
        except Exception as e:
            self._send(500, {"error": f"Lookup failed: {e}"})

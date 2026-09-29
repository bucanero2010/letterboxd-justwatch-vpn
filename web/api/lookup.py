"""Vercel Python function: GET /api/lookup?q=<title>&year=<yyyy>&countries=ES,US,..."""

import json
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

from simplejustwatchapi import offers_for_countries, search


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

            match = results[0]
            offers = offers_for_countries(match.entry_id, countries)
            out = {}
            for country, country_offers in offers.items():
                providers = sorted({o.package.name for o in country_offers
                                    if o.monetization_type in ("FLATRATE", "FREE", "ADS")})
                if providers:
                    out[country] = providers
            self._send(200, {"title": match.title, "year": match.release_year, "offers": out})
        except Exception as e:
            self._send(500, {"error": f"Lookup failed: {e}"})

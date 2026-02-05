# letterboxd-justwatch-vpn
Find where your unwatched Letterboxd films are streaming worldwide using JustWatch.

# Letterboxd → JustWatch VPN Finder 🎬🌍

This tool helps you:
- Extract movies from your **Letterboxd watchlist**
- Exclude films you’ve already watched
- Find **where each movie is available to stream worldwide**
- Filter to **flat-rate streaming only** (no rent / buy)
- Use your VPN to watch on platforms you already own

## Supported Streaming Services
Configured by the user (e.g. Netflix, HBO, Prime Video, MUBI, Filmin, RTVE Play).

## How it works
1. Scrapes Letterboxd watchlist and watched films
2. Computes remaining unwatched titles
3. Queries JustWatch availability by country
4. Displays where each movie can be streamed

## Installation
```bash
pip install -r requirements.txt

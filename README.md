# Letterboxd → JustWatch VPN Finder 🎬🌍

Automate the search for your Letterboxd watchlist across global streaming services. This tool identifies which films are available on "Flatrate" subscriptions (Netflix, Max, Disney+, etc.) in multiple countries, helping you maximize your VPN and subscriptions.

## 🚀 Features
- **Smart Scanning:** Daily checks for new additions; Full library syncs on Sundays or the 1st of every month.
- **Global Reach:** Scans 9+ countries (US, UK, JP, ES, CA, AU, etc.) in a single automated run.
- **Automatic Metadata:** Fetches high-quality posters and runtimes via the TMDB API.
- **Streamlit UI:** A searchable dashboard to filter by country, service, or movie duration.

## 🛠️ Technical Challenges & Solutions
Building a robust scraper for dynamic, localized sites like JustWatch presented several engineering hurdles:

* **The "Accept All" Barrier:** JustWatch uses aggressive cookie banners that overlay the entire UI. I implemented an iterative "Accept" logic that targets various localized button names (Accept, Aceptar, 同意) before attempting layout changes.
* **Dynamic Layout Switching:** The streaming "Grid" view provides more data but is often hidden behind a `div` rather than a standard `button`. I used Playwright's `locator().filter()` with Regex to reliably toggle the "Grid" view across multiple languages.
* **Lazy Loading Data:** JustWatch only loads offer rows as the user scrolls. The script includes a headless "Scroll-to-Bottom" trigger and network-idle waits to ensure all providers are captured before the HTML is parsed.
* **The GB vs. UK Emoji Bug:** Discovered that Unicode regional indicators for "UK" do not render as a flag emoji in most browsers (they require "GB"). I implemented a mapping layer in the UI to ensure the 🇬🇧 flag displays correctly.

## 📦 Installation & Usage
1. **Clone the repository** to your local machine.
2. **Install dependencies** using the requirements file provided.
3. **Install Playwright browsers** (specifically Chromium).
4. **Configure your settings** in the configuration file with your Letterboxd username and TMDB API key.
5. **Run the scraper** to fetch the latest streaming data.
6. **Launch the UI** via Streamlit to browse your results.

## ⚙️ CI/CD
This project is configured with **GitHub Actions** (`scrape.yml`) to run automatically every day at 3 AM UTC. It securely handles API keys via GitHub Secrets and commits the updated data back to the repository.
"""
Alert service: detects newly available movies on owned streaming services
and sends an email notification.
"""

import os
import re
import smtplib
import pandas as pd
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path

# Owned services — must match the provider names in the CSV
OWNED_SERVICES = [
    "Netflix",
    "Amazon Prime Video",
    "HBO Max",
    "Apple TV",
    "Disney Plus",
    "YouTube",
    "rtve",
]

# Sources to exclude from alerts
EXCLUDED_SOURCES = {"Alyssa"}


def match_owned(provider: str) -> bool:
    """Check if a provider name matches any owned service."""
    provider_lower = provider.lower()
    for svc in OWNED_SERVICES:
        if svc.lower() in provider_lower:
            return True
    return False


def find_new_availability(old_csv: Path, new_csv: Path) -> pd.DataFrame:
    """
    Compare old and new CSVs to find movies that are newly available
    on owned services (excluding certain sources).
    """
    if not old_csv.exists():
        return pd.DataFrame()

    df_old = pd.read_csv(old_csv)
    df_new = pd.read_csv(new_csv)

    # Filter to owned services only
    df_old_owned = df_old[df_old["provider"].apply(match_owned)].copy()
    df_new_owned = df_new[df_new["provider"].apply(match_owned)].copy()

    # Exclude Alyssa source
    if "source" in df_new_owned.columns:
        df_new_owned = df_new_owned[
            ~df_new_owned["source"].fillna("").apply(
                lambda s: all(src.strip() in EXCLUDED_SOURCES for src in s.split(","))
            )
        ]

    # Build keys for comparison
    def make_key(row):
        return f"{row['title']}|{row['year']}|{row['country']}|{row['provider']}"

    old_keys = set(df_old_owned.apply(make_key, axis=1))
    df_new_owned["_key"] = df_new_owned.apply(make_key, axis=1)

    # New = in new but not in old
    newly_available = df_new_owned[~df_new_owned["_key"].isin(old_keys)].copy()
    newly_available.drop(columns=["_key"], inplace=True)

    return newly_available


def country_to_flag(code: str) -> str:
    code = code.upper()
    if code == "UK":
        code = "GB"
    if len(code) != 2:
        return code
    return "".join(chr(ord(c) + 127397) for c in code)


def build_email_html(newly_available: pd.DataFrame) -> str:
    """Build a nice HTML email body from the newly available movies."""
    # Group by movie
    grouped = newly_available.groupby(["title", "year"]).apply(
        lambda g: g[["country", "provider"]].to_dict("records"), include_groups=False
    ).reset_index(name="offers")

    movies_html = ""
    for _, row in grouped.iterrows():
        title = row["title"]
        year = int(row["year"])

        # Group offers by country
        by_country: dict[str, list[str]] = {}
        for offer in row["offers"]:
            c = offer["country"]
            by_country.setdefault(c, []).append(offer["provider"])

        offers_lines = ""
        for country in sorted(by_country.keys()):
            flag = country_to_flag(country)
            providers = ", ".join(sorted(set(by_country[country])))
            offers_lines += f"<li>{flag} {country}: <strong>{providers}</strong></li>"

        movies_html += f"""
        <div style="margin-bottom: 20px; padding: 12px; border-left: 3px solid #6366f1; background: #f8f8fc;">
            <strong style="font-size: 16px;">{title}</strong> <span style="opacity: 0.6;">({year})</span>
            <ul style="margin: 6px 0 0 0; padding-left: 20px;">{offers_lines}</ul>
        </div>
        """

    return f"""
    <html>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: #6366f1;">🍿 New Streaming Alerts</h2>
        <p>These movies from your watchlist just became available on your streaming services:</p>
        {movies_html}
        <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
        <p style="font-size: 12px; opacity: 0.5;">Sent by your Letterboxd Watchlist Scraper</p>
    </body>
    </html>
    """


def send_alert_email(newly_available: pd.DataFrame):
    """Send an email alert for newly available movies."""
    email_address = os.environ.get("EMAIL_ADDRESS")
    email_password = os.environ.get("EMAIL_APP_PASSWORD")

    if not email_address or not email_password:
        print("⚠️ Email credentials not set. Skipping alert.")
        return

    if newly_available.empty:
        print("📭 No new availability to alert about.")
        return

    n_movies = newly_available.groupby(["title", "year"]).ngroups
    print(f"📧 Sending alert for {n_movies} newly available movie(s)...")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🍿 {n_movies} movie(s) now streaming on your services"
    msg["From"] = email_address
    msg["To"] = email_address

    html_body = build_email_html(newly_available)
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(email_address, email_password)
            server.send_message(msg)
        print("✅ Alert email sent!")
    except Exception as e:
        print(f"⚠️ Failed to send email: {e}")

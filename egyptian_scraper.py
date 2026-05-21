"""Egyptian Theatre (Park City) scraper.

Scrapes https://parkcityshows.com — the Egyptian's primary ticketing site,
backed by HoldMyTicket. The listings page lists ~20-25 upcoming shows. Each
event detail page has a clean "Event Showtimes" section with one
<div class="show_time"> per show containing day, date, time, and ticket link.

No Cloudflare, plain HTTP — straight requests + BeautifulSoup.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

MOUNTAIN = ZoneInfo("America/Denver")
SOURCE = "Egyptian Theatre"
LISTINGS_URL = "https://parkcityshows.com/shows-ticketing/upcoming-shows"
BASE = "https://parkcityshows.com"
VENUE_NAME = "Egyptian Theatre"
VENUE_ADDRESS = "328 Main Street, Park City, UT 84060"
VENUE_LAT, VENUE_LNG = 40.6428, -111.4965

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
}

# Pattern to pull "May 21, 2026 / 8:00PM" or "May 21, 2026 / 8:00 PM" out of a show_time div
SHOW_PATTERN = re.compile(
    r'([A-Z][a-z]{2,8})\s+(\d{1,2}),?\s*(\d{4})\s*/\s*(\d{1,2}:\d{2}\s*[AP]M)',
    re.IGNORECASE,
)


def _fetch(url: str) -> str | None:
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        if r.status_code == 200:
            return r.text
        print(f"  WARN: {url} -> HTTP {r.status_code}")
        return None
    except Exception as e:
        print(f"  ERROR fetching {url}: {e}")
        return None


def _extract_event_urls(listings_html: str) -> list[str]:
    """Pull unique event detail URLs from the listings page."""
    pattern = re.compile(r'href="(/shows-ticketing/upcoming-shows/event/[^"]+)"')
    paths = set(pattern.findall(listings_html))
    return [BASE + p for p in sorted(paths)]


def _parse_datetime(month: str, day: str, year: str, time_str: str) -> tuple[str, str] | None:
    """Build a (date, normalized_time) tuple from raw strings."""
    for fmt in ("%b %d %Y", "%B %d %Y"):
        try:
            dt = datetime.strptime(f"{month} {day} {year}", fmt)
            date_str = dt.strftime("%Y-%m-%d")
            # Normalize "8:00PM" -> "8:00 PM"
            t = re.sub(r'\s+', '', time_str).upper()
            t = t.replace("PM", " PM").replace("AM", " AM").strip()
            return (date_str, t)
        except ValueError:
            continue
    return None


def _extract_showtimes(html: str) -> list[tuple[str, str, str | None]]:
    """Pull (date, time, ticket_url) tuples from the Event Showtimes section.

    Returns one tuple per individual show date (e.g., a 3-night run -> 3 tuples).
    """
    out: list[tuple[str, str, str | None]] = []
    soup = BeautifulSoup(html, "html.parser")
    show_times = soup.select("div.show_time")
    for st in show_times:
        text = st.get_text(" ", strip=True)
        m = SHOW_PATTERN.search(text)
        if not m:
            continue
        parsed = _parse_datetime(m.group(1), m.group(2), m.group(3), m.group(4))
        if not parsed:
            continue
        date_str, time_str = parsed
        # Try to find the per-show ticket URL
        a = st.find("a", class_="buy_tickets")
        ticket_url = a["href"] if a and a.get("href") else None
        out.append((date_str, time_str, ticket_url))
    return out


def _extract_event(url: str, html: str) -> list[dict]:
    """Parse an individual event detail page into 1+ records (one per show date)."""
    soup = BeautifulSoup(html, "html.parser")

    # Title
    h1 = soup.find("h1", class_="eventtitle")
    og_title = soup.find("meta", property="og:title")
    title = (h1.get_text(strip=True) if h1 else
             og_title["content"].strip() if og_title and og_title.get("content") else "")
    if not title:
        return []

    # Description (OpenGraph or .description div)
    og_desc = soup.find("meta", property="og:description")
    description = og_desc["content"].strip() if og_desc and og_desc.get("content") else ""

    # Image
    og_image = soup.find("meta", property="og:image")
    image_url = og_image["content"].strip() if og_image and og_image.get("content") else None

    # Showtimes
    showtimes = _extract_showtimes(html)
    if not showtimes:
        return []

    records = []
    for date_str, time_str, ticket_url in showtimes:
        records.append({
            "title": title,
            "date": date_str,
            "start_time": time_str,
            "description": description[:500] if description else None,
            "venue_name": VENUE_NAME,
            "address": VENUE_ADDRESS,
            "lat": VENUE_LAT,
            "lng": VENUE_LNG,
            "link": ticket_url or url,
            "image_url": image_url,
            "source": SOURCE,
            "source_url": LISTINGS_URL,
            # Egyptian hosts both music acts and theater productions — let the
            # classifier figure out which from the title/description.
        })
    return records


def scrape() -> list[dict]:
    print(f"Scraping {LISTINGS_URL}...", flush=True)
    listings_html = _fetch(LISTINGS_URL)
    if not listings_html:
        return []

    urls = _extract_event_urls(listings_html)
    print(f"  Found {len(urls)} unique event URLs", flush=True)

    today = datetime.now(MOUNTAIN).date().isoformat()
    cutoff = (datetime.now(MOUNTAIN).date() + timedelta(days=180)).isoformat()

    all_records: list[dict] = []
    for i, url in enumerate(urls, 1):
        slug = url.rsplit('/', 1)[-1]
        print(f"  [{i}/{len(urls)}] {slug}", flush=True)
        html = _fetch(url)
        if not html:
            continue
        recs = _extract_event(url, html)
        all_records.extend(recs)
        print(f"      -> {len(recs)} show date(s)", flush=True)

    # Keep only events within today..cutoff window
    in_window = [r for r in all_records if today <= r["date"] <= cutoff]
    print(f"\nTotal: {len(all_records)} records, {len(in_window)} in 180-day window", flush=True)
    return in_window


def main():
    events = scrape()
    out = Path("public/raw/events-egyptian.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"events": events, "scraped_at": datetime.now(MOUNTAIN).isoformat()}, indent=2))
    print(f"Wrote {len(events)} events to {out}")


if __name__ == "__main__":
    main()

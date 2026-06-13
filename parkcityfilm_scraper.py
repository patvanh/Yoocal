"""Park City Film scraper.

Scrapes https://parkcityfilm.org — the venue's own site (Jim Santy Auditorium).
The /showtimes/upcoming/ page lists upcoming films, each linking to a film detail
page (/film/<slug>/) whose "Film Info" block has the authoritative date + showtime
(e.g. "Jun 27, 2026" / "4pm"). This is the PRIMARY source — aggregators (VPC,
Park Record) re-list these films and sometimes get the time wrong (VPC showed 7pm
for a 4pm screening), so scraping the venue directly gives the correct data.

Plain HTTP + BeautifulSoup (WordPress site, no JS needed for the Film Info block).
Mirrors egyptian_scraper.py's structure (listing -> detail -> records, 180d window).
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
SOURCE = "Park City Film"
LISTINGS_URL = "https://parkcityfilm.org/showtimes/upcoming/"
BASE = "https://parkcityfilm.org"
VENUE_NAME = "Jim Santy Auditorium"
VENUE_ADDRESS = "1255 Park Avenue, Park City, UT 84060"
VENUE_LAT, VENUE_LNG = 40.6507, -111.5054

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
}

_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct",
     "nov", "dec"], start=1)}


def _fetch(url: str) -> str | None:
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        if r.status_code == 200:
            return r.text
        print(f"      fetch {url} -> HTTP {r.status_code}", flush=True)
    except Exception as ex:
        print(f"      fetch {url} error: {str(ex)[:60]}", flush=True)
    return None


def _extract_film_urls(listings_html: str) -> list[str]:
    """Pull /film/<slug>/ detail URLs from the upcoming-films listing."""
    soup = BeautifulSoup(listings_html, "html.parser")
    urls, seen = [], set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/film/" in href and href.rstrip("/").split("/")[-1] not in ("film", ""):
            full = href if href.startswith("http") else BASE + href
            full = full.split("?")[0]
            if full not in seen:
                seen.add(full)
                urls.append(full)
    return urls


def _parse_date(text: str, year_hint: int) -> str | None:
    """Parse 'Jun 27, 2026' or 'June 27, 2026' -> '2026-06-27'."""
    m = re.search(r"([A-Za-z]{3,9})\s+(\d{1,2}),?\s*(\d{4})?", text)
    if not m:
        return None
    mon = _MONTHS.get(m.group(1)[:3].lower())
    if not mon:
        return None
    day = int(m.group(2))
    year = int(m.group(3)) if m.group(3) else year_hint
    try:
        return f"{year:04d}-{mon:02d}-{day:02d}"
    except ValueError:
        return None


def _parse_time(text: str) -> str | None:
    """Parse '4pm' / '7:00 PM' / '4:30pm' -> 'H:MM PM'."""
    m = re.search(r"(\d{1,2})(?::(\d{2}))?\s*([ap])\.?m\.?", text, re.IGNORECASE)
    if not m:
        return None
    hour = int(m.group(1))
    minute = m.group(2) or "00"
    ampm = m.group(3).upper() + "M"
    return f"{hour}:{minute} {ampm}"


def _extract_film(url: str, html: str) -> list[dict]:
    """Parse a /film/<slug>/ page. Returns 1+ records (one per listed date)."""
    soup = BeautifulSoup(html, "html.parser")

    h1 = soup.find("h1")
    title = h1.get_text(strip=True) if h1 else ""
    if not title:
        og = soup.find("meta", property="og:title")
        title = og["content"].split(" - ")[0].strip() if og and og.get("content") else ""
    if not title:
        return []

    og_desc = soup.find("meta", property="og:description")
    description = og_desc["content"].strip() if og_desc and og_desc.get("content") else ""
    og_image = soup.find("meta", property="og:image")
    image_url = og_image["content"].strip() if og_image and og_image.get("content") else None

    page_text = soup.get_text("\n", strip=True)

    # The "Film Info" block lists "Dates" then "Showtimes". Pull date(s) + time.
    # Dates can be a single day or a run "Jun 5 - Jun 7"; we capture each date
    # that appears near the Film Info section.
    year_now = datetime.now(MOUNTAIN).year
    # showtime
    time_str = None
    mtime = re.search(r"Showtimes?\s*\n+\s*([^\n]+)", page_text, re.IGNORECASE)
    if mtime:
        time_str = _parse_time(mtime.group(1))
    if not time_str:
        time_str = _parse_time(page_text)  # fallback: first time on page

    # dates: look in the Film Info "Dates" section first
    dates = []
    mdates = re.search(r"Dates?\s*\n+\s*([^\n]+(?:\n[^\n]+){0,3})", page_text, re.IGNORECASE)
    date_blob = mdates.group(1) if mdates else page_text[:400]
    for mm in re.finditer(r"[A-Za-z]{3,9}\s+\d{1,2},?\s*\d{4}", date_blob):
        d = _parse_date(mm.group(0), year_now)
        if d and d not in dates:
            dates.append(d)
    if not dates:
        # fallback: first date anywhere on page
        m = re.search(r"[A-Za-z]{3,9}\s+\d{1,2},?\s*\d{4}", page_text)
        if m:
            d = _parse_date(m.group(0), year_now)
            if d:
                dates = [d]
    if not dates:
        return []

    # ticket link (eventive) if present
    ticket = None
    for a in soup.find_all("a", href=True):
        if "eventive" in a["href"]:
            ticket = a["href"]
            break

    records = []
    for d in dates:
        records.append({
            "title": title,
            "date": d,
            "start_time": time_str,
            "description": description[:2000] if description else None,
            "venue_name": VENUE_NAME,
            "address": VENUE_ADDRESS,
            "lat": VENUE_LAT,
            "lng": VENUE_LNG,
            "link": ticket or url,
            "image_url": image_url,
            "source": SOURCE,
            "source_url": url,
            "categories": ["Film"],
        })
    return records


def scrape() -> list[dict]:
    print(f"Scraping {LISTINGS_URL}...", flush=True)
    listings_html = _fetch(LISTINGS_URL)
    if not listings_html:
        return []

    urls = _extract_film_urls(listings_html)
    print(f"  Found {len(urls)} unique film URLs", flush=True)

    today = datetime.now(MOUNTAIN).date().isoformat()
    cutoff = (datetime.now(MOUNTAIN).date() + timedelta(days=180)).isoformat()

    all_records: list[dict] = []
    for i, url in enumerate(urls, 1):
        slug = url.rstrip("/").rsplit("/", 1)[-1]
        print(f"  [{i}/{len(urls)}] {slug}", flush=True)
        html = _fetch(url)
        if not html:
            continue
        recs = _extract_film(url, html)
        all_records.extend(recs)
        print(f"      -> {len(recs)} date(s)"
              f"{' @ ' + recs[0]['start_time'] if recs and recs[0].get('start_time') else ''}",
              flush=True)

    in_window = [r for r in all_records if today <= r["date"] <= cutoff]
    print(f"\nTotal: {len(all_records)} records, {len(in_window)} in 180-day window",
          flush=True)
    return in_window


def main():
    events = scrape()
    out = Path("public/raw/events-parkcityfilm.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(
        {"events": events, "scraped_at": datetime.now(MOUNTAIN).isoformat()}, indent=2))
    print(f"Wrote {len(events)} events to {out}", flush=True)


if __name__ == "__main__":
    main()

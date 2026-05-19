#!/usr/bin/env python3
"""
Mountain Town Music scraper — Park City local-music nonprofit.

Walks https://mountaintownmusic.org/show-sitemap*.xml, filters to recently
updated URLs, fetches each show page, and parses the visible-text concert
info (date, time, venue, address, free flag).

The site has ~2,450 historical URLs across 3 sitemaps. We filter by lastmod
within the recent window so we don't crawl every past concert.

Output schema matches our standard event dict.
"""

import requests
import re
import html
import time
from datetime import datetime, timedelta
from urllib.parse import urlparse

UA = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

SITEMAP_URLS = [
    "https://mountaintownmusic.org/show-sitemap.xml",
    "https://mountaintownmusic.org/show-sitemap2.xml",
    "https://mountaintownmusic.org/show-sitemap3.xml",
]

# Park City coordinates as default (the org is based in PC even if a
# specific show address might be elsewhere — we override per-event when
# we can extract a real address)
DEFAULT_LAT = 40.6461
DEFAULT_LNG = -111.4980

LASTMOD_WINDOW_DAYS = 120

# Regex that parses the show page body text
SHOW_RE = re.compile(
    r"([A-Z][a-z]+ \d{1,2}, \d{4})\s+"           # date (group 1)
    r"(\d{1,2}:\d{2}\s*[ap]m)"                   # start (group 2)
    r"(?:\s*[\u2013\u2014\-]\s*"                 # optional dash
    r"(\d{1,2}:\d{2}\s*[ap]m))?\s+"              # end time (group 3, optional)
    r"(.{5,150}?)"                               # venue + address (group 4)
    r"(?:FREE SHOW|Facebook|TICKETS)",           # terminator
    re.IGNORECASE,
)

MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}


def _parse_date(s):
    """Parse 'July 7, 2026' -> '2026-07-07' (ISO)."""
    m = re.match(r"([A-Za-z]+) (\d{1,2}), (\d{4})", s.strip())
    if not m:
        return None
    mon = MONTHS.get(m.group(1).lower())
    if not mon:
        return None
    return f"{int(m.group(3)):04d}-{mon:02d}-{int(m.group(2)):02d}"


def _normalize_time(t):
    """'7:00 pm' -> '7:00 PM'."""
    if not t:
        return ""
    return re.sub(r"\s+", " ", t.strip().upper())


def _split_venue_address(raw):
    """
    Mountain Town Music shows publish 'Venue Name // Address' or sometimes
    just an address. Split when possible.
    """
    raw = raw.strip().rstrip(",")
    if "//" in raw:
        a, b = raw.split("//", 1)
        return a.strip(), b.strip()
    return "", raw  # no venue name; the whole thing is an address-ish string


def _fetch_sitemap_urls():
    """Return (url, lastmod_datetime) pairs across all 3 sitemaps."""
    cutoff = datetime.utcnow() - timedelta(days=LASTMOD_WINDOW_DAYS)
    pairs = []
    for sm in SITEMAP_URLS:
        try:
            r = requests.get(sm, headers=UA, timeout=15)
            if r.status_code != 200:
                continue
            xml = r.text
        except Exception as ex:
            print(f"  [MTM] sitemap fetch failed: {sm}: {ex}")
            continue

        # Walk <url> blocks
        for block in re.findall(r"<url>(.*?)</url>", xml, re.DOTALL):
            loc_m = re.search(r"<loc>([^<]+)</loc>", block)
            mod_m = re.search(r"<lastmod>([^<]+)</lastmod>", block)
            if not loc_m or not mod_m:
                continue
            try:
                # Lastmod looks like "2025-10-16T16:44:30+00:00"
                lm = datetime.fromisoformat(mod_m.group(1).replace("Z", "+00:00")).replace(tzinfo=None)
            except Exception:
                continue
            if lm < cutoff:
                continue
            pairs.append((loc_m.group(1), lm))

    # Newest first
    pairs.sort(key=lambda x: x[1], reverse=True)
    return pairs


def _parse_show(url):
    """Fetch + parse a single show page. Returns event dict or None."""
    try:
        r = requests.get(url, headers=UA, timeout=15)
        if r.status_code != 200:
            return None
    except Exception:
        return None

    decoded = html.unescape(r.text)
    text = re.sub(r"<script.*?</script>", "", decoded, flags=re.DOTALL)
    text = re.sub(r"<style.*?</style>", "", text, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    h1m = re.search(r"<h1[^>]*>([^<]+)</h1>", decoded)
    title = h1m.group(1).strip() if h1m else ""
    if not title:
        return None

    m = SHOW_RE.search(text)
    if not m:
        return None

    date_iso = _parse_date(m.group(1))
    if not date_iso:
        return None

    start_time = _normalize_time(m.group(2))
    end_time = _normalize_time(m.group(3))
    venue_name, address = _split_venue_address(m.group(4))
    is_free = "FREE SHOW" in text

    return {
        "title": title,
        "date": date_iso,
        "description": f"{title} live at {venue_name or address}.",
        "location": (f"{venue_name}, {address}" if venue_name and address else (venue_name or address)),
        "link": url,
        "source": "Mountain Town Music",
        "source_url": "https://mountaintownmusic.org/",
        "lat": DEFAULT_LAT,
        "lng": DEFAULT_LNG,
        "categories": ["Music"],
        "is_free": is_free,
        "price": "Free" if is_free else "",
        "start_time": start_time,
        "end_time": end_time,
        "address": address,
        "venue_name": venue_name,
        "scraped_at": datetime.now().isoformat(),
    }


def scrape_mountain_town_music():
    print("Scraping Mountain Town Music...")
    today_iso = datetime.now().strftime("%Y-%m-%d")
    pairs = _fetch_sitemap_urls()
    print(f"  [MTM] {len(pairs)} URLs in last {LASTMOD_WINDOW_DAYS} days")

    from concurrent.futures import ThreadPoolExecutor, as_completed
    events = []
    parse_misses = 0
    past_dropped = 0

    # Parallel fetches: 5 concurrent. CloudFlare in front of this site
    # handles bursts fine; we just need to stay courteous.
    def _job(u):
        return u, _parse_show(u)

    with ThreadPoolExecutor(max_workers=5) as ex:
        futures = [ex.submit(_job, url) for url, _ in pairs]
        for f in as_completed(futures):
            try:
                url, ev = f.result()
            except Exception:
                parse_misses += 1
                continue
            if not ev:
                parse_misses += 1
                continue
            if ev["date"] < today_iso:
                past_dropped += 1
                continue
            events.append(ev)

    print(f"  [MTM] parsed {len(events)} future events, dropped {past_dropped} past, {parse_misses} parse misses")
    return events


if __name__ == "__main__":
    out = scrape_mountain_town_music()
    print(f"\n{len(out)} future events found:")
    for e in out[:10]:
        print(f"  [{e['date']} {e['start_time']}] {e['title']} -- {e['venue_name'] or e['address']}")

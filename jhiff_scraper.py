#!/usr/bin/env python3
"""
Jackson Hole International Film Festival scraper.

Walks https://jhiff.org/sitemap.xml, filters to URLs under
/jackson-hole-screenings-and-events/, fetches each, and parses the
Schema.org Event JSON-LD that's already on every event page.

Output schema matches our standard event dict.
"""

import requests
import re
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from schema_org_scraper import scrape_schema_org_events

UA = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

SITEMAP_URL = "https://jhiff.org/sitemap.xml"
EVENT_URL_PATTERN = "/jackson-hole-screenings-and-events/"

# Jackson Hole town coordinates as default — most events are at Center
# for the Arts or other in-town venues, but we let the JSON-LD location
# override when present.
DEFAULT_LAT = 43.4799
DEFAULT_LNG = -110.7624


def _fetch_event_urls():
    """Return list of individual event-page URLs from sitemap."""
    try:
        r = requests.get(SITEMAP_URL, headers=UA, timeout=15)
        if r.status_code != 200:
            print(f"  [JHiFF] sitemap fetch failed: HTTP {r.status_code}")
            return []
        locs = re.findall(r"<loc>([^<]+)</loc>", r.text)
    except Exception as ex:
        print(f"  [JHiFF] sitemap fetch failed: {ex}")
        return []

    # Filter to individual events (not the index page itself)
    urls = []
    for u in locs:
        if EVENT_URL_PATTERN in u and u.rstrip("/") != f"https://jhiff.org{EVENT_URL_PATTERN}".rstrip("/"):
            urls.append(u)
    return urls


def scrape_jhiff():
    print("Scraping Jackson Hole International Film Festival...")
    urls = _fetch_event_urls()
    print(f"  [JHiFF] found {len(urls)} event URLs in sitemap")

    events = []
    parse_misses = 0

    def _job(url):
        # schema_org_scraper handles JSON-LD parsing, past-date filtering,
        # and standard field shaping. We just point it at one URL at a time
        # since each jhiff page is a single event.
        try:
            return scrape_schema_org_events(
                url=url,
                source_name="Jackson Hole International Film Festival",
                default_lat=DEFAULT_LAT,
                default_lng=DEFAULT_LNG,
                default_city="Jackson, WY",
                default_categories=["Film", "Arts"],
                max_events=1,
                timeout=15,
            )
        except Exception:
            return None

    with ThreadPoolExecutor(max_workers=5) as ex:
        futures = [ex.submit(_job, u) for u in urls]
        for f in as_completed(futures):
            try:
                batch = f.result()
            except Exception:
                parse_misses += 1
                continue
            if not batch:
                parse_misses += 1
                continue
            events.extend(batch)

    print(f"  [JHiFF] parsed {len(events)} future events, {parse_misses} parse misses / past events")
    return events


if __name__ == "__main__":
    out = scrape_jhiff()
    print(f"\n{len(out)} future events found:")
    for e in out[:10]:
        print(f"  [{e.get('date')} {e.get('start_time','')}] {e.get('title')} -- {e.get('venue_name','?') or e.get('address','?')[:60]}")

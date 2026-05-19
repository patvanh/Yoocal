"""Park Record (cityspark.com) event scraper.

The Park Record's calendar at parkrecord.com/calendar/ is a JS-rendered
SPA powered by CitySpark. The portal script at portal.cityspark.com/
PortalScripts/ParkRecord identifies the calendar with ppid=8838 and
slug='ParkRecord'.

Event data comes from a POST endpoint:
  POST https://portal.cityspark.com/api/events/GetEvents/ParkRecord
  Content-Type: application/json
  Body: { ppid, lat, lng, distance, search, skip, ... }
  Response: { Success, Value: [event...] }

Caveat: CitySpark labels `DateStart` with a `Z` suffix as if it were UTC,
but the actual value is local Mountain Time. The real UTC lives in
`StartUTC`. We use DateStart for the display time.
"""
from __future__ import annotations

import re
import time
from datetime import datetime
from typing import Iterable, List

import requests


CITYSPARK_URL = "https://portal.cityspark.com/api/events/GetEvents/ParkRecord"
PORTAL_ID = 8838
PARK_CITY_LAT = 40.6461
PARK_CITY_LNG = -111.4980
SEARCH_RADIUS_MILES = 15  # was 50, but that pulled entire Wasatch Front
PAGE_SIZE = 25  # CitySpark returns 25 per page (server-capped)

# Known recurring Park City events that the unfiltered crawl misses because
# the API's default sort surfaces popular/proximity-ranked events first and
# caps pagination at ~1200. Each term triggers one extra search pass.
TARGETED_SEARCHES = [
    "park silly",
    "farmers market",
    "kimball",       # Kimball Arts Center / Kimball Junction events
    "deer valley",
    "sundance",
    "egyptian theatre",
    "swaner",        # Swaner Preserve
    "mountain town music",
]

HEADERS = {
    "Content-Type": "application/json",
    "Origin": "https://www.parkrecord.com",
    "Referer": "https://www.parkrecord.com/",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0 Safari/537.36"
    ),
}


def _fmt_time(iso_str: str) -> str:
    """Convert '2026-06-21T10:00:00Z' to '10:00 AM'."""
    if not iso_str:
        return ""
    m = re.match(r"(\d{4}-\d{2}-\d{2})T(\d{2}):(\d{2})", iso_str)
    if not m:
        return ""
    hh, mm = int(m.group(2)), int(m.group(3))
    ampm = "AM" if hh < 12 else "PM"
    h12 = hh % 12 or 12
    return f"{h12}:{mm:02d} {ampm}"


def _categorize(tags: list, name: str, venue: str) -> list:
    """Map CitySpark numeric tag IDs + name heuristics to yoocal categories."""
    cats = set()
    name_l = (name or "").lower()
    venue_l = (venue or "").lower()
    text = name_l + " " + venue_l

    if any(k in text for k in ("market", "fair", "festival")):
        cats.add("Outdoor"); cats.add("Food & Drink")
    if any(k in text for k in ("band", "music", "concert", "dj", "jazz", "rock", "live")):
        cats.add("Music")
    if any(k in text for k in ("storytime", "kids", "family", "child")):
        cats.add("Family")
    if any(k in text for k in ("yoga", "fitness", "wellness")):
        cats.add("Wellness")
    if any(k in text for k in ("art", "gallery", "exhibit")):
        cats.add("Arts")
    if any(k in text for k in ("hike", "ski", "trail", "outdoor")):
        cats.add("Outdoor")

    return sorted(cats) if cats else ["Community"]


import math

PARK_CITY_CENTER_LAT = 40.6461
PARK_CITY_CENTER_LNG = -111.4980
MAX_DISTANCE_MILES = 12  # hard cap; CitySpark sometimes returns events well beyond the radius param


def _haversine_miles(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in miles."""
    R = 3958.7613
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlng / 2) ** 2)
    return 2 * R * math.asin(math.sqrt(a))


def _normalize_event(cs: dict) -> dict | None:
    """Convert a CitySpark event dict to a yoocal event dict.

    Returns None if the event lacks the minimum fields (name + date) or if
    the venue is more than MAX_DISTANCE_MILES from Park City center (the
    CitySpark API\'s distance filter is permissive — we hard-filter here).
    """
    name = (cs.get("Name") or "").strip()
    date_start = cs.get("DateStart") or ""
    if not name or not date_start:
        return None

    # Extract YYYY-MM-DD for `date`
    date_iso = date_start[:10]
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_iso):
        return None

    # Times — note: DateStart is local time despite Z suffix
    start_time = _fmt_time(date_start) if cs.get("HasTime") else ""

    date_end = cs.get("DateEnd") or ""
    end_time = ""
    end_date_iso = None
    if date_end and re.match(r"^\d{4}-\d{2}-\d{2}", date_end):
        end_date_iso = date_end[:10] if date_end[:10] != date_iso else None
        # Only use end_time if HasTime AND end is after start (sanity check)
        if cs.get("HasTime") and date_end > date_start:
            end_time = _fmt_time(date_end)

    venue = (cs.get("Venue") or "").strip()
    address = (cs.get("Address") or "").strip()
    city_state = (cs.get("CityState") or "").strip()
    if venue and city_state:
        location = f"{venue}, {city_state}"
    elif venue:
        location = venue
    elif city_state:
        location = city_state
    else:
        location = "Park City, UT"

    description = (cs.get("Description") or cs.get("Short") or "").strip()
    if len(description) > 600:
        description = description[:597] + "..."

    # Best link: PrimaryUrl > first Links entry > Park Record fallback
    link = cs.get("PrimaryUrl") or ""
    if not link:
        links = cs.get("Links") or []
        if links and isinstance(links, list) and isinstance(links[0], dict):
            link = links[0].get("url") or ""
    if not link:
        link = "https://www.parkrecord.com/calendar/"

    # Hard geo filter: drop events outside ~12 miles of Park City center.
    # CitySpark sometimes returns events 30-50 miles away despite the
    # distance request, which leaks Salt Lake metro events into PC.
    ev_lat = cs.get("latitude")
    ev_lng = cs.get("longitude")
    if ev_lat and ev_lng:
        try:
            dist = _haversine_miles(
                float(ev_lat), float(ev_lng),
                PARK_CITY_CENTER_LAT, PARK_CITY_CENTER_LNG
            )
            if dist > MAX_DISTANCE_MILES:
                return None
        except (TypeError, ValueError):
            pass  # if lat/lng malformed, keep the event

    event = {
        "title": name,
        "date": date_iso,
        "description": description,
        "location": location,
        "link": link,
        "source": "The Park Record",
        "source_url": "https://www.parkrecord.com/calendar/",
        "lat": cs.get("latitude") or PARK_CITY_LAT,
        "lng": cs.get("longitude") or PARK_CITY_LNG,
        "categories": _categorize(cs.get("Tags") or [], name, venue),
        "start_time": start_time,
        "end_time": end_time,
        "scraped_at": datetime.now().isoformat(),
    }
    if end_date_iso:
        event["end_date"] = end_date_iso
    if venue:
        event["venue_name"] = venue
    if address:
        event["address"] = address
    img = cs.get("LargeImg") or cs.get("MediumImg") or cs.get("SmallImg")
    if img:
        event["image_url"] = img
    return event


def fetch_page(skip: int = 0, search: str = "", timeout: int = 20,
               start: str | None = None) -> List[dict]:
    """Fetch one page of events from CitySpark."""
    body = {
        "ppid": PORTAL_ID,
        "tps": None,
        "lat": PARK_CITY_LAT,
        "lng": PARK_CITY_LNG,
        "distance": SEARCH_RADIUS_MILES,
        "search": search,
        "sort": None,  # None = upcoming-soonest order; "date" descends to far-future
        "category": None,
        "labels": [],
        "pick": None,
        "sparks": None,
        # CitySpark requires a non-null `start` — bad request otherwise.
        "start": start or datetime.now().strftime("%Y-%m-%dT00:00"),
        "end": None,
        "defFilter": None,
        "skip": skip,
    }
    try:
        r = requests.post(CITYSPARK_URL, json=body, headers=HEADERS, timeout=timeout)
        r.raise_for_status()
        data = r.json()
    except Exception as ex:
        print(f"  [Park Record/CitySpark] fetch failed (skip={skip}): {ex}")
        return []
    if not data.get("Success"):
        print(f"  [Park Record/CitySpark] API error: {data.get('ErrorMessage')}")
        return []
    return data.get("Value") or []


def _crawl_targeted(search: str, start_iso: str, max_pages: int, seen_pids: set,
                    all_events: list, today_iso: str, label: str,
                    pid_occurrence_count: dict | None = None,
                    title_occurrence_count: dict | None = None) -> int:
    """Paginate one search query within a date window."""
    if pid_occurrence_count is None:
        pid_occurrence_count = {}
    if title_occurrence_count is None:
        title_occurrence_count = {}
    skip = 0
    added = 0
    for page in range(max_pages):
        raw = fetch_page(skip=skip, search=search, start=start_iso)
        if not raw:
            break
        new_this_page = 0
        for cs in raw:
            pid = cs.get("PId")
            date_start = cs.get("DateStart") or ""
            # CitySpark uses the SAME PId for recurring events (one umbrella
            # event has many DateStart occurrences). Dedup on (PId, date) so
            # each occurrence becomes its own record.
            dedup_key = (pid, date_start[:10] if date_start else "")
            if pid is None or dedup_key in seen_pids:
                continue
            # Per-PId occurrence cap (30 = roughly 7 months of weekly events).
            # Catches recurring events like yoga that share one PId.
            pid_count = pid_occurrence_count.get(pid, 0)
            if pid_count >= 30:
                continue
            # Title-occurrence cap (12). Catches theater runs and recurring
            # meetings where each performance/meeting has a different PId
            # but the same title (e.g. Scarlet Pimpernel: 51 nights).
            title_key = (cs.get("Name") or "").strip().lower()
            title_count = title_occurrence_count.get(title_key, 0)
            if title_key and title_count >= 12:
                continue
            seen_pids.add(dedup_key)
            pid_occurrence_count[pid] = pid_count + 1
            if title_key:
                title_occurrence_count[title_key] = title_count + 1
            ev = _normalize_event(cs)
            if not ev:
                continue
            eff = ev.get("end_date") or ev["date"]
            if eff < today_iso:
                continue
            all_events.append(ev)
            new_this_page += 1
            added += 1
        if len(raw) < PAGE_SIZE:
            break
        if new_this_page == 0:
            break
        skip += len(raw)
        time.sleep(0.3)
    if added > 0:
        print(f"  [Park Record/CitySpark] {label}: +{added} (running total: {len(all_events)})")
    return added


def _crawl_with_start(start_iso: str, max_pages: int, seen_pids: set,
                       all_events: list, today_iso: str, label: str,
                       pid_occurrence_count: dict | None = None,
                       title_occurrence_count: dict | None = None) -> int:
    """Paginate the unfiltered API starting from a given date window."""
    if pid_occurrence_count is None:
        pid_occurrence_count = {}
    if title_occurrence_count is None:
        title_occurrence_count = {}
    skip = 0
    added = 0
    for page in range(max_pages):
        raw = fetch_page(skip=skip, search="", start=start_iso)
        if not raw:
            break
        new_this_page = 0
        for cs in raw:
            pid = cs.get("PId")
            date_start = cs.get("DateStart") or ""
            # CitySpark uses the SAME PId for recurring events (one umbrella
            # event has many DateStart occurrences). Dedup on (PId, date) so
            # each occurrence becomes its own record.
            dedup_key = (pid, date_start[:10] if date_start else "")
            if pid is None or dedup_key in seen_pids:
                continue
            # Per-PId occurrence cap (30 = roughly 7 months of weekly events).
            # Catches recurring events like yoga that share one PId.
            pid_count = pid_occurrence_count.get(pid, 0)
            if pid_count >= 30:
                continue
            # Title-occurrence cap (12). Catches theater runs and recurring
            # meetings where each performance/meeting has a different PId
            # but the same title (e.g. Scarlet Pimpernel: 51 nights).
            title_key = (cs.get("Name") or "").strip().lower()
            title_count = title_occurrence_count.get(title_key, 0)
            if title_key and title_count >= 12:
                continue
            seen_pids.add(dedup_key)
            pid_occurrence_count[pid] = pid_count + 1
            if title_key:
                title_occurrence_count[title_key] = title_count + 1
            ev = _normalize_event(cs)
            if not ev:
                continue
            eff = ev.get("end_date") or ev["date"]
            if eff < today_iso:
                continue
            all_events.append(ev)
            new_this_page += 1
            added += 1
        if len(raw) < PAGE_SIZE:
            break
        if new_this_page == 0:
            break
        skip += len(raw)
        time.sleep(0.4)
    print(f"  [Park Record/CitySpark] {label}: +{added} (running total: {len(all_events)})")
    return added


def _crawl(search: str, max_pages: int, seen_pids: set, all_events: list,
           today_iso: str, label: str) -> int:
    """Paginate one search query. Mutates seen_pids and all_events."""
    skip = 0
    added = 0
    for page in range(max_pages):
        raw = fetch_page(skip=skip, search=search)
        if not raw:
            break
        new_this_page = 0
        for cs in raw:
            pid = cs.get("PId")
            date_start = cs.get("DateStart") or ""
            # CitySpark uses the SAME PId for recurring events (one umbrella
            # event has many DateStart occurrences). Dedup on (PId, date) so
            # each occurrence becomes its own record.
            dedup_key = (pid, date_start[:10] if date_start else "")
            if pid is None or dedup_key in seen_pids:
                continue
            # Per-PId occurrence cap (30 = roughly 7 months of weekly events).
            # Catches recurring events like yoga that share one PId.
            pid_count = pid_occurrence_count.get(pid, 0)
            if pid_count >= 30:
                continue
            # Title-occurrence cap (12). Catches theater runs and recurring
            # meetings where each performance/meeting has a different PId
            # but the same title (e.g. Scarlet Pimpernel: 51 nights).
            title_key = (cs.get("Name") or "").strip().lower()
            title_count = title_occurrence_count.get(title_key, 0)
            if title_key and title_count >= 12:
                continue
            seen_pids.add(dedup_key)
            pid_occurrence_count[pid] = pid_count + 1
            if title_key:
                title_occurrence_count[title_key] = title_count + 1
            ev = _normalize_event(cs)
            if not ev:
                continue
            eff = ev.get("end_date") or ev["date"]
            if eff < today_iso:
                continue
            all_events.append(ev)
            new_this_page += 1
            added += 1
        if len(raw) < PAGE_SIZE:
            break
        if new_this_page == 0:
            break
        skip += len(raw)
        time.sleep(0.4)
    print(f"  [Park Record/CitySpark] {label}: +{added} (running total: {len(all_events)})")
    return added


def scrape_park_record_cityspark(max_pages: int = 200) -> list:
    """Fetch all Park Record events via CitySpark API. Returns yoocal events.

    Strategy:
      1. Unfiltered crawl (gets the bulk: ~1200 popularity/proximity-ranked).
      2. Targeted searches for known recurring events the unfiltered crawl
         misses (Park Silly, Farmers Market, Kimball, etc.).
    Dedup by CitySpark PId so a single event surfaced by both passes counts
    once.
    """
    print("Scraping Park Record (CitySpark API)...")
    today_iso = datetime.now().strftime("%Y-%m-%d")
    all_events: list = []
    seen_pids: set = set()
    pid_occurrence_count: dict = {}
    title_occurrence_count: dict = {}

    # Monthly windowed crawls — CitySpark caps pagination at ~1200 globally,
    # so advancing `start` past today lets us reach later months that the
    # unfiltered crawl would otherwise miss.
    from datetime import date, timedelta
    today = date.today()
    for months_ahead in range(0, 8):  # today, today+1mo, ..., today+7mo
        year = today.year + (today.month - 1 + months_ahead) // 12
        month = (today.month - 1 + months_ahead) % 12 + 1
        # First window: clamp to today so the API doesn't reject a past start.
        if months_ahead == 0:
            window_start = today.strftime("%Y-%m-%dT00:00")
        else:
            window_start = f"{year:04d}-{month:02d}-01T00:00"
        _crawl_with_start(window_start, max_pages, seen_pids, all_events,
                          today_iso, f"month={year}-{month:02d}",
                          pid_occurrence_count=pid_occurrence_count,
                          title_occurrence_count=title_occurrence_count)
    # Targeted searches iterated by month so we don't burn pages on May 19
    # dupes already collected by the unfiltered crawls.
    for term in TARGETED_SEARCHES:
        for months_ahead in range(0, 6):
            year = today.year + (today.month - 1 + months_ahead) // 12
            month = (today.month - 1 + months_ahead) % 12 + 1
            window_start = f"{year:04d}-{month:02d}-01T00:00"
            _crawl_targeted(term, window_start, 10, seen_pids, all_events,
                            today_iso, f"search={term!r} month={year}-{month:02d}",
                            pid_occurrence_count=pid_occurrence_count,
                          title_occurrence_count=title_occurrence_count)

    print(f"  [Park Record/CitySpark] total: {len(all_events)} future events")
    return all_events


if __name__ == "__main__":
    events = scrape_park_record_cityspark()
    print(f"\n=== {len(events)} events ===")
    for e in events[:20]:
        print(f"  {e['date']} {e.get('start_time','') or '--':<10} | {e['title'][:55]}")

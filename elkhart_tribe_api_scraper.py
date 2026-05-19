"""Elkhart Lake Tribe Calendar (WordPress REST API) scraper.

elkhartlake.com runs The Events Calendar (Tribe) WordPress plugin.
Tribe exposes a public REST API at /wp-json/tribe/events/v1/events
that returns clean structured event data with proper ISO dates.

The old `scrape_elkhartlake_com()` function in elkhart_scraper.py was
scraping HTML and producing entries like `date: "See website"` because
date extraction from rendered markup is brittle. This module replaces
that approach by hitting the JSON endpoint directly.

Returns yoocal-format event dicts. Pagination via per_page+page params.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import List

import requests


ELKHART_BASE_URL = "https://www.elkhartlake.com/wp-json/tribe/events/v1/events"
OSTHOFF_BASE_URL = "https://osthoff.com/wp-json/tribe/events/v1/events"
PER_PAGE = 50  # Tribe's max per page

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 yoocal-bot/1.0"
    ),
    "Accept": "application/json",
}


def _strip_html(html: str) -> str:
    """Strip tags + decode entities for description fields."""
    import html as html_lib
    text = re.sub(r"<[^>]+>", " ", html or "")
    text = html_lib.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _normalize_time(iso_time: str) -> str:
    """Convert '2026-05-22 18:00:00' to '6:00 PM'."""
    if not iso_time:
        return ""
    m = re.match(r"\d{4}-\d{2}-\d{2}[\sT](\d{2}):(\d{2})", iso_time)
    if not m:
        return ""
    hh, mm = int(m.group(1)), int(m.group(2))
    if hh == 0 and mm == 0:
        return ""  # midnight = no real time
    ampm = "AM" if hh < 12 else "PM"
    h12 = hh % 12 or 12
    return f"{h12}:{mm:02d} {ampm}"


def _normalize_event(tribe_ev: dict, source_name: str = "Elkhart Lake Tourism",
                     source_url: str = "https://www.elkhartlake.com/events/",
                     default_location: str = "Elkhart Lake, WI") -> dict | None:
    """Convert a Tribe API event dict to yoocal event format."""
    title = _strip_html(tribe_ev.get("title") or "")
    start_iso = tribe_ev.get("start_date") or ""
    if not title or not start_iso:
        return None

    # Date: YYYY-MM-DD
    date = start_iso[:10]
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date):
        return None

    end_iso = tribe_ev.get("end_date") or ""
    end_date = end_iso[:10] if end_iso and end_iso[:10] != date else None

    description = _strip_html(tribe_ev.get("description") or "")
    if len(description) > 600:
        description = description[:597] + "..."

    # Venue
    venue_obj = tribe_ev.get("venue") or {}
    venue_name = ""
    location_str = default_location
    if isinstance(venue_obj, dict):
        venue_name = (venue_obj.get("venue") or "").strip()
        v_addr = venue_obj.get("address") or ""
        v_city = venue_obj.get("city") or "Elkhart Lake"
        v_state = venue_obj.get("state_province") or venue_obj.get("state") or "WI"
        if venue_name and v_addr:
            location_str = f"{venue_name}, {v_addr}, {v_city}, {v_state}"
        elif venue_name:
            location_str = f"{venue_name}, {v_city}, {v_state}"

    # Featured image
    img = ""
    image_obj = tribe_ev.get("image")
    if isinstance(image_obj, dict):
        img = image_obj.get("url") or ""
    elif isinstance(image_obj, str):
        img = image_obj

    # Cost / price
    cost = (tribe_ev.get("cost") or "").strip()

    event = {
        "title": title,
        "date": date,
        "start_time": _normalize_time(start_iso),
        "end_time": _normalize_time(end_iso) if end_iso else "",
        "description": description,
        "location": location_str,
        "link": tribe_ev.get("url") or source_url,
        "source": source_name,
        "source_url": source_url,
        "scraped_at": datetime.now().isoformat(),
    }
    if end_date:
        event["end_date"] = end_date
    if venue_name:
        event["venue_name"] = venue_name
    if img:
        event["image_url"] = img
    if cost:
        event["price"] = cost

    return event


def _scrape_tribe_api(base_url: str, label: str, source_name: str,
                     source_url: str, months_ahead: int = 12,
                     default_location: str = "Elkhart Lake, WI") -> List[dict]:
    """Generic Tribe REST API scraper. Returns yoocal event dicts."""
    print(f"Scraping {label} (Tribe REST API)...")

    today = datetime.now().date()
    end_date = today + timedelta(days=months_ahead * 31)
    today_iso = today.isoformat()

    params = {
        "per_page": PER_PAGE,
        "start_date": today_iso,
        "end_date": end_date.isoformat(),
        "page": 1,
    }

    events: List[dict] = []
    seen_ids: set = set()
    pages = 0
    max_pages = 30

    while pages < max_pages:
        params["page"] = pages + 1
        try:
            r = requests.get(base_url, headers=HEADERS, params=params, timeout=20)
            if r.status_code == 400:
                # Tribe returns 400 when page > available pages — normal exit
                break
            r.raise_for_status()
            data = r.json()
        except Exception as ex:
            print(f"  [Elkhart/Tribe] fetch failed on page {pages + 1}: {ex}")
            break

        page_events = data.get("events") or []
        if not page_events:
            break

        added = 0
        for tribe_ev in page_events:
            ev_id = tribe_ev.get("id")
            if ev_id and ev_id in seen_ids:
                continue
            if ev_id:
                seen_ids.add(ev_id)
            normalized = _normalize_event(tribe_ev, source_name=source_name, source_url=source_url, default_location=default_location)
            if normalized:
                events.append(normalized)
                added += 1

        print(f"  [{label}] page {pages + 1}: {len(page_events)} fetched, {added} added "
              f"(cumulative: {len(events)})")
        pages += 1
        if len(page_events) < PER_PAGE:
            break

    print(f"  [{label}] total: {len(events)} events")
    return events


def scrape_elkhartlake_tribe_api(months_ahead: int = 12) -> List[dict]:
    """Fetch upcoming events from elkhartlake.com Tribe API."""
    return _scrape_tribe_api(
        base_url=ELKHART_BASE_URL,
        label="elkhartlake.com",
        source_name="Elkhart Lake Tourism",
        source_url="https://www.elkhartlake.com/events/",
        months_ahead=months_ahead,
        default_location="Elkhart Lake, WI",
    )


def scrape_osthoff_tribe_api(months_ahead: int = 12) -> List[dict]:
    """Fetch upcoming events from osthoff.com Tribe API.

    Provides Lake Deck Music Series + other Osthoff Resort events that aren't
    yet syndicated to elkhartlake.com. Important for August/September Lake
    Deck shows that Tribe at elkhartlake.com hasn't picked up yet.
    """
    return _scrape_tribe_api(
        base_url=OSTHOFF_BASE_URL,
        label="osthoff.com",
        source_name="The Osthoff Resort",
        source_url="https://osthoff.com/calendar/",
        months_ahead=months_ahead,
        default_location="The Osthoff Resort, Elkhart Lake, WI",
    )


if __name__ == "__main__":
    elk = scrape_elkhartlake_tribe_api()
    osth = scrape_osthoff_tribe_api()
    print(f"\n=== elkhartlake.com: {len(elk)} events ===")
    print(f"=== osthoff.com:     {len(osth)} events ===")
    # Lake Deck count combined
    all_events = elk + osth
    lake_deck = [e for e in all_events if 'lake deck' in (e['title'] + ' ' + (e.get('description') or '')).lower()]
    print(f"\n=== Combined Lake Deck: {len(lake_deck)} ===")
    seen = set()
    for e in sorted(lake_deck, key=lambda x: (x['date'], x.get('start_time') or '')):
        key = (e['date'], e['title'])
        if key in seen: continue
        seen.add(key)
        print(f"  {e['date']} {e.get('start_time') or '--':<10} | {e['title'][:60]}")

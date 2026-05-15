"""
Park City Institute (Park City Performing Arts) events scraper.

PCI uses Showpass for ticketing. Showpass has a clean, undocumented but
public JSON API. We hit it directly:

    GET https://www.showpass.com/api/public/events/?venue=6807

The 'venue=6807' parameter is the venue ID for Park City Performing Arts.

This pulls in their full event roster — currently the "Concerts on the
Slopes" summer concert series at The Amphitheatre at Canyons Village
at Park City Mountain, including names like Allen Stone, 38 Special,
UB40, Boney James, Rick Springfield, etc.

Public entry point:
    scrape_park_city_institute() -> list of event dicts
"""

import re
import requests
from datetime import datetime

API_URL = "https://www.showpass.com/api/public/events/"
VENUE_ID = 6807  # Park City Performing Arts
SOURCE_NAME = "Park City Institute"

# Coordinates for The Amphitheatre at Canyons Village at Park City Mountain
# (Canyons Village, on the north side of Park City Mountain)
AMPHITHEATRE_LAT = 40.6707
AMPHITHEATRE_LNG = -111.5559

# Default location string when the event's API location is missing/sparse
DEFAULT_LOCATION = "The Amphitheatre at Canyons Village at Park City Mountain"


def scrape_park_city_institute():
    """Fetch and parse PCI events. Returns a list of event dicts."""
    print("Scraping Park City Institute (Showpass)...")
    events = []

    try:
        raw_events = _fetch_all_pages()
    except Exception as ex:
        print(f"  Error fetching Park City Institute events: {ex}")
        return []

    print(f"  Got {len(raw_events)} raw events from Showpass")

    today_iso = datetime.now().strftime("%Y-%m-%d")
    seen = set()
    dropped_past = 0
    dropped_inactive = 0

    for raw in raw_events:
        # Only published, active events
        if not raw.get("is_published"):
            dropped_inactive += 1
            continue
        status = raw.get("status", "")
        if status and status != "sp_event_active":
            dropped_inactive += 1
            continue

        parsed = _parse_event(raw)
        if not parsed:
            continue
        if parsed["date"] < today_iso:
            dropped_past += 1
            continue

        # Dedup
        key = (parsed["title"].lower().strip()[:40], parsed["date"][:10])
        if key in seen:
            continue
        seen.add(key)
        events.append(parsed)

    print(
        f"  Returning {len(events)} clean events "
        f"({dropped_past} past, {dropped_inactive} inactive dropped)"
    )
    return events


def _fetch_all_pages():
    """Pull all pages of the Showpass events list for this venue."""
    all_events = []
    page = 1
    while True:
        r = requests.get(
            API_URL,
            params={"venue": VENUE_ID, "page": page},
            headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
            timeout=20,
        )
        r.raise_for_status()
        data = r.json()
        results = data.get("results", [])
        if not results:
            break
        all_events.extend(results)
        if data.get("next") is None or data.get("num_pages", 1) <= page:
            break
        page += 1
        if page > 20:  # safety
            break
    return all_events


def _parse_event(raw):
    """Convert one Showpass event dict to our standard schema."""
    try:
        title = (raw.get("name") or "").strip()
        if not title or len(title) < 3:
            return None

        # local_starts_on is in ISO with timezone offset (e.g. '2026-07-10T19:00:00-06:00')
        # That's exactly what we want — local time, no conversion needed.
        local_start = raw.get("local_starts_on") or ""
        if not local_start:
            return None
        try:
            start_dt = datetime.fromisoformat(local_start)
        except Exception:
            return None

        date_iso = start_dt.strftime("%Y-%m-%d")
        start_time = start_dt.strftime("%-I:%M %p")

        # End time — combine starts_on + duration_seconds, then convert to local
        end_time = None
        duration_sec = raw.get("duration_seconds")
        if duration_sec:
            try:
                from datetime import timedelta
                end_dt = start_dt + timedelta(seconds=int(duration_sec))
                end_time = end_dt.strftime("%-I:%M %p")
            except Exception:
                pass

        # Description — strip HTML, take first ~280 chars
        desc = (raw.get("description_without_html") or "").strip()
        if not desc:
            desc_html = raw.get("description") or ""
            desc = re.sub(r"<[^>]+>", " ", desc_html)
            desc = re.sub(r"\s+", " ", desc).strip()
        description = desc[:280]

        # Location — Showpass returns a dict; build a venue string
        loc_obj = raw.get("location") or {}
        loc_name = (loc_obj.get("name") or "").strip() if isinstance(loc_obj, dict) else ""
        if loc_name:
            location = loc_name
        else:
            location = DEFAULT_LOCATION

        # Always tag with the geographic descriptor for Park City clarity
        if "park city" not in location.lower():
            location += ", Park City, UT"

        # Link to event detail (where users buy tickets)
        link = (raw.get("frontend_details_url") or "").strip()
        if not link:
            slug = (raw.get("slug") or "").strip()
            link = f"https://www.showpass.com/{slug}/" if slug else "https://www.showpass.com/o/park-city-performing-arts/"

        # Categories — always "Music" for PCI concerts
        categories = ["Music"]

        # Price range (ticket_types is a list of pricing tiers)
        price_min, price_max = None, None
        for tt in (raw.get("ticket_types") or []):
            if not isinstance(tt, dict):
                continue
            try:
                p = float(tt.get("price") or 0)
                if p <= 0:
                    continue
                if price_min is None or p < price_min:
                    price_min = p
                if price_max is None or p > price_max:
                    price_max = p
            except Exception:
                pass

        event = {
            "title": title,
            "date": date_iso,
            "start_time": start_time,
            "description": description,
            "location": location,
            "link": link,
            "source": SOURCE_NAME,
            "source_url": "https://www.parkcityinstitute.org/bsbn",
            "lat": AMPHITHEATRE_LAT,
            "lng": AMPHITHEATRE_LNG,
            "categories": categories,
        }
        if end_time:
            event["end_time"] = end_time
        if price_min is not None:
            if price_max and price_max != price_min:
                event["price_range"] = f"${int(price_min)}-${int(price_max)}"
            else:
                event["price_range"] = f"${int(price_min)}"

        return event

    except Exception:
        return None


if __name__ == "__main__":
    # Stand-alone test
    results = scrape_park_city_institute()
    print(f"\nTotal: {len(results)} events")
    print()
    for e in results[:20]:
        time_s = e.get("start_time", "(all day)")
        end_s = e.get("end_time", "")
        price = e.get("price_range", "-")
        time_str = f"{time_s}-{end_s}" if end_s else time_s
        print(f"  {e['date']} {time_str:>20s} | {e['title'][:50]:50s} | {price}")

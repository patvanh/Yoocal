"""
Salt Lake Running Co (slrc.com) event scraper.

slrc.com hosts the broadest Utah race calendar we've found — 300+ events
across the state. Their /event-calendar/ page uses an Elfsight widget
which pulls data from Elfsight's public boot API. Single GET, no auth.

API:
    GET https://core.service.elfsight.com/p/boot/
        ?page=https://slrc.com/event-calendar/
        &w=a10bfee0-42e2-4f53-820e-677491b15693

Returns JSON containing widget settings which includes:
  - events: list of event objects
  - locations: lookup table {id → {name, address, ...}}
  - eventTypes: lookup table {id → {name, ...}} (5K, 10K, Half Marathon, etc)
  - hosts: lookup table {id → {name, ...}}

Each event has:
  name, description (HTML), start{date,time}, end{date,time}, isAllDay,
  location[id], eventType[id], host[id], tags[], image{url},
  buttonLink{value}, buttonText, id, repeatPeriod

Note: When isAllDay is True, the "time" field appears to be the event
creation timestamp (e.g. 14:14), NOT the race start time. We ignore time
when isAllDay is True and emit the event as date-only.

Since slrc covers all Utah, we filter to Park City + Heber + nearby.
Public entry points:
    scrape_slrc_parkcity() -> list of event dicts
    scrape_slrc_heber()    -> list of event dicts
"""

import requests
import re
from datetime import datetime

API_URL = "https://core.service.elfsight.com/p/boot/"
WIDGET_ID = "a10bfee0-42e2-4f53-820e-677491b15693"
SOURCE_NAME = "Salt Lake Running Co"
SOURCE_URL = "https://slrc.com/event-calendar/"

# Cities we care about for each region.
# slrc tags events with location IDs that map to names like "Park City", "Heber City", etc.
PARK_CITY_LOCATION_NAMES = {
    "park city", "deer valley", "snyderville", "summit park",
}
HEBER_LOCATION_NAMES = {
    "heber city", "heber", "midway", "kamas", "charleston", "daniel",
    "wallsburg",
}


def scrape_slrc_parkcity():
    """Park City + nearby events from slrc.com."""
    print("Scraping Salt Lake Running Co (Park City races)...")
    return _scrape_for(PARK_CITY_LOCATION_NAMES, default_lat=40.6461, default_lng=-111.4980)


def scrape_slrc_heber():
    """Heber Valley events from slrc.com."""
    print("Scraping Salt Lake Running Co (Heber Valley races)...")
    return _scrape_for(HEBER_LOCATION_NAMES, default_lat=40.5069, default_lng=-111.4133)


def _scrape_for(target_location_names, default_lat, default_lng):
    """Run the slrc.com API call and filter to the target locations."""
    try:
        data = _fetch_elfsight()
    except Exception as ex:
        print(f"  Error fetching slrc.com: {ex}")
        return []

    widget = data.get("data", {}).get("widgets", {}).get(WIDGET_ID, {})
    settings = widget.get("data", {}).get("settings", {})

    events = settings.get("events", [])
    locations = settings.get("locations", [])
    event_types = settings.get("eventTypes", [])

    # Build lookup tables
    loc_lookup = {loc["id"]: loc for loc in locations}
    type_lookup = {t["id"]: t for t in event_types}

    print(f"  Total events from slrc API: {len(events)}")
    print(f"  Locations table: {len(locations)} cities")
    print(f"  Event types table: {len(event_types)} types")

    today_iso = datetime.now().strftime("%Y-%m-%d")
    out = []
    dropped_past = 0
    dropped_wrong_region = 0

    for ev in events:
        # Resolve location names
        loc_ids = ev.get("location") or []
        if not loc_ids:
            dropped_wrong_region += 1
            continue
        loc_names = []
        for lid in loc_ids:
            loc = loc_lookup.get(lid)
            if loc and loc.get("name"):
                loc_names.append(loc["name"])

        # Region filter: is any of this event's locations in our target set?
        loc_names_lower = {n.lower() for n in loc_names}
        if not (loc_names_lower & target_location_names):
            dropped_wrong_region += 1
            continue

        # Parse the event
        parsed = _parse_event(ev, loc_names, type_lookup, default_lat, default_lng)
        if not parsed:
            continue
        if parsed["date"] < today_iso:
            dropped_past += 1
            continue

        out.append(parsed)

    print(f"  Matched target region: {len(out)} events (dropped {dropped_past} past, {dropped_wrong_region} out-of-region)")
    return out


def _fetch_elfsight():
    """Single GET to the Elfsight boot API."""
    r = requests.get(
        API_URL,
        params={"page": "https://slrc.com/event-calendar/", "w": WIDGET_ID},
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh) Chrome/124.0",
            "Accept": "application/json",
            "Referer": "https://slrc.com/event-calendar/",
        },
        timeout=20,
    )
    r.raise_for_status()
    return r.json()


def _parse_event(ev, loc_names, type_lookup, default_lat, default_lng):
    """Convert one Elfsight event to our standard schema."""
    try:
        title = (ev.get("name") or "").strip()
        if not title or len(title) < 3:
            return None

        # Date — start.date is "2026-05-23"
        start = ev.get("start") or {}
        date_iso = start.get("date") or ""
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_iso):
            return None

        # Time — only emit if NOT isAllDay (since isAllDay events have garbage timestamps)
        # AND the time is plausible (between 5am and 10pm typically)
        is_all_day = bool(ev.get("isAllDay"))
        start_time = None
        if not is_all_day:
            time_str = start.get("time") or ""
            if re.match(r"^\d{1,2}:\d{2}$", time_str):
                try:
                    h, m = time_str.split(":")
                    h, m = int(h), int(m)
                    dt = datetime(2000, 1, 1, h, m)
                    start_time = dt.strftime("%-I:%M %p")
                except Exception:
                    pass

        # End time
        end_time = None
        end_date_iso = None
        end = ev.get("end") or {}
        if end.get("date") and end["date"] != date_iso:
            end_date_iso = end["date"]
        if not is_all_day and start_time:
            end_time_str = end.get("time") or ""
            if re.match(r"^\d{1,2}:\d{2}$", end_time_str):
                try:
                    h, m = end_time_str.split(":")
                    h, m = int(h), int(m)
                    end_time = datetime(2000, 1, 1, h, m).strftime("%-I:%M %p")
                except Exception:
                    pass

        # Description — strip HTML
        desc_html = ev.get("description") or ""
        description = re.sub(r"<[^>]+>", " ", desc_html)
        description = re.sub(r"\s+", " ", description).strip()
        if len(description) > 600:
            description = description[:597] + "..."
        if not description:
            description = "Race in Utah. See registration page for details."

        # Location — best location name + city, UT
        loc_str = ", ".join(loc_names) + ", UT" if loc_names else "Utah"

        # Categories — derive from event type and tags
        categories = ["Running"]
        ev_type_ids = ev.get("eventType") or []
        for tid in ev_type_ids:
            t = type_lookup.get(tid)
            if t and t.get("name"):
                name_lower = t["name"].lower()
                if "triathlon" in name_lower:
                    categories = ["Sports", "Triathlon"]
                    break
                elif "bike" in name_lower or "cycling" in name_lower:
                    categories = ["Cycling", "Outdoor"]
                    break
                elif "trail" in name_lower:
                    categories = ["Running", "Outdoor"]

        # Link — buttonLink.value is the registration page
        button_link = ev.get("buttonLink") or {}
        link = button_link.get("value") or button_link.get("rawValue") or SOURCE_URL

        # Image
        image_obj = ev.get("image") or {}
        image_url = image_obj.get("url") or ""

        event = {
            "title": title,
            "date": date_iso,
            "description": description,
            "location": loc_str,
            "link": link,
            "source": SOURCE_NAME,
            "source_url": SOURCE_URL,
            "lat": default_lat,
            "lng": default_lng,
            "categories": categories,
        }
        if start_time:
            event["start_time"] = start_time
        if end_time:
            event["end_time"] = end_time
        if end_date_iso:
            event["end_date"] = end_date_iso
        if image_url:
            event["image_url"] = image_url

        return event

    except Exception:
        return None


if __name__ == "__main__":
    print("=" * 60)
    pc = scrape_slrc_parkcity()
    print(f"\n{len(pc)} PC events:")
    for e in pc:
        time_s = e.get("start_time", "(all day)")
        print(f"  {e['date']} {time_s:>9s} | {e['title'][:65]}")

    print()
    print("=" * 60)
    heber = scrape_slrc_heber()
    print(f"\n{len(heber)} Heber events:")
    for e in heber:
        time_s = e.get("start_time", "(all day)")
        print(f"  {e['date']} {time_s:>9s} | {e['title'][:65]}")

"""
Mountain Trails Foundation events scraper (parkcitytrails.org).

Mountain Trails Foundation curates Park City's trail-related events — both
their own volunteer trail-building days AND the major endurance events that
happen on those trails (Park City Trail Series, Triple Trail Challenge,
Tour des Suds, etc).

The site uses the WordPress "Calendarize it" plugin which exposes a public
JSON endpoint. Single GET request, no auth, no Cloudflare.

API:
    GET https://parkcitytrails.org/?rhc_action=get_calendar_events
        &post_type[]=events
        &start={unix_ts}
        &end={unix_ts}
        &rhc_shrink

Returns: {"R": "OK", "MSG": "", "EVENTS": [...]}

Each event has these clean fields (we use these):
    title           — e.g. "Volunteer Opportunity: Ontario Mine Trailhead"
    start           — "2026-08-16 08:30:00"
    end             — "2026-08-16 12:00:00"
    fc_start        — "2026-08-16"
    fc_start_time   — "08:30"
    fc_end          — "2026-08-16"
    fc_end_time     — "12:00"
    allDay          — bool
    url             — usually a Facebook event link or registration link
    description     — HTML (often empty for these events)
    image_full      — usually empty
    id              — "6181-events"
    local_id        — 6181

Public entry point:
    scrape_park_city_trails() -> list of event dicts
"""

import requests
import time
import re
from datetime import datetime

API_URL = "https://parkcitytrails.org/"
SOURCE_NAME = "Mountain Trails Foundation"
SOURCE_URL = "https://parkcitytrails.org/events-calendar/"

# Default coordinates for "Park City trails" — center of Round Valley trail system
DEFAULT_LAT = 40.6700
DEFAULT_LNG = -111.4910


def scrape_park_city_trails():
    """Fetch and parse Mountain Trails Foundation events."""
    print("Scraping Mountain Trails Foundation (parkcitytrails.org)...")
    events = []

    try:
        raw_events = _fetch_events()
    except Exception as ex:
        print(f"  Error fetching MTF events: {ex}")
        return []

    print(f"  Got {len(raw_events)} raw events from MTF API")

    today_iso = datetime.now().strftime("%Y-%m-%d")
    seen = set()
    dropped_past = 0

    for raw in raw_events:
        parsed = _parse_event(raw)
        if not parsed:
            continue
        if parsed["date"] < today_iso:
            dropped_past += 1
            continue
        key = (parsed["title"].lower().strip()[:40], parsed["date"][:10])
        if key in seen:
            continue
        seen.add(key)
        events.append(parsed)

    print(f"  Returning {len(events)} clean events ({dropped_past} past dropped)")
    return events


def _fetch_events():
    """Hit the Calendarize-it API for the next 180 days."""
    now = int(time.time())
    end = now + (180 * 86400)  # 180 days out

    params = {
        "rhc_action": "get_calendar_events",
        "post_type[]": "events",
        "start": now,
        "end": end,
        "rhc_shrink": "",
    }

    r = requests.get(
        API_URL,
        params=params,
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": SOURCE_URL,
        },
        timeout=20,
    )
    r.raise_for_status()

    data = r.json()
    if data.get("R") != "OK":
        raise Exception(f"API returned R={data.get('R')}, MSG={data.get('MSG','')}")

    return data.get("EVENTS", [])


def _parse_event(raw):
    """Convert one MTF event to our standard schema."""
    try:
        title = (raw.get("title") or "").strip()
        if not title or len(title) < 3:
            return None

        # Date and time
        start_str = raw.get("start") or ""
        end_str = raw.get("end") or ""
        all_day = bool(raw.get("allDay"))

        # Parse "2026-08-16 08:30:00" format
        try:
            start_dt = datetime.strptime(start_str, "%Y-%m-%d %H:%M:%S")
        except Exception:
            return None

        date_iso = start_dt.strftime("%Y-%m-%d")
        start_time = None
        if not all_day and start_dt.hour != 0 or start_dt.minute != 0:
            # Only emit a time if it's not 00:00:00 (which means "no time set")
            if not (start_dt.hour == 0 and start_dt.minute == 0):
                start_time = start_dt.strftime("%-I:%M %p")

        end_time = None
        end_date_iso = None
        if end_str:
            try:
                end_dt = datetime.strptime(end_str, "%Y-%m-%d %H:%M:%S")
                end_date_iso = end_dt.strftime("%Y-%m-%d")
                if start_time:  # only show end_time if we have start_time
                    if not (end_dt.hour == 0 and end_dt.minute == 0):
                        end_time = end_dt.strftime("%-I:%M %p")
            except Exception:
                pass

        # Description — strip HTML
        desc_html = raw.get("description") or ""
        description = re.sub(r"<[^>]+>", " ", desc_html)
        description = re.sub(r"\s+", " ", description).strip()
        if not description:
            # Fallback — derive a useful description from title patterns
            if "volunteer" in title.lower():
                description = "Trail-building volunteer event with Mountain Trails Foundation"
            elif any(race in title.lower() for race in ["5k", "10k", "half marathon", "25k", "50k", "trail series", "challenge", "rambler"]):
                description = "Trail race in Park City — see event link for registration and details"
            elif "tour des suds" in title.lower():
                description = "Annual Park City cycling tradition — see event link for details"
            else:
                description = "Park City trails community event"

        # Location — MTF events are all on Park City trails
        # Try to derive a more specific venue from the title
        location = "Park City Trails, Park City, UT"
        title_lower = title.lower()
        if "round valley" in title_lower:
            location = "Round Valley, Park City, UT"
        elif "deer valley" in title_lower or "silver lake" in title_lower or "mid mountain" in title_lower:
            location = "Mid Mountain Trail / Deer Valley, Park City, UT"
        elif "jupiter peak" in title_lower or "park city mountain" in title_lower:
            location = "Park City Mountain, Park City, UT"
        elif "tour des suds" in title_lower:
            location = "Park City, UT"

        # Categories — derive from title
        categories = []
        if "volunteer" in title_lower:
            categories.append("Volunteer")
        if any(r in title_lower for r in ["5k", "10k", "half marathon", "25k", "50k", "rambler", "challenge", "trail series"]):
            categories.append("Running")
        if "tour des suds" in title_lower or "bike" in title_lower or "cycling" in title_lower:
            categories.append("Cycling")
        if not categories:
            categories = ["Outdoor"]

        # Link — usually a Facebook event or signup link
        link = (raw.get("url") or "").strip()
        if not link:
            link = SOURCE_URL

        event = {
            "title": title,
            "date": date_iso,
            "description": description,
            "location": location,
            "link": link,
            "source": SOURCE_NAME,
            "source_url": SOURCE_URL,
            "lat": DEFAULT_LAT,
            "lng": DEFAULT_LNG,
            "categories": categories,
        }
        if start_time:
            event["start_time"] = start_time
        if end_time:
            event["end_time"] = end_time
        if end_date_iso and end_date_iso != date_iso:
            event["end_date"] = end_date_iso

        return event

    except Exception:
        return None


if __name__ == "__main__":
    results = scrape_park_city_trails()
    print(f"\nTotal: {len(results)} events\n")
    for e in results:
        time_s = e.get("start_time", "(all day)")
        cats = ",".join(e.get("categories", []))
        print(f"  {e['date']} {time_s:>10s} | {e['title'][:55]:55s} | {cats[:20]:20s} | {e.get('location','?')[:30]}")

"""
Deer Valley Resort events scraper.

Deer Valley's events page (deervalley.com/things-to-do/events) embeds its event
data as HTML-entity-encoded JSON inside a hidden <var class="results"> element.
We extract it, decode the entities, parse it as JSON, and convert each event
to our standard schema.

This is a one-page-fetch scraper — no Playwright needed, no pagination. All 56
events come in a single request.

Public entry point:
    scrape_deer_valley() -> list of event dicts

Field schema returned (matches the rest of scraper.py):
    title, date (YYYY-MM-DD), end_date, start_time, end_time,
    location, description, link, source, source_url, lat, lng,
    categories, end_recurring (Weekly/null)
"""

import re
import html
import json
import requests
from datetime import datetime

EVENTS_URL = "https://www.deervalley.com/things-to-do/events"
BASE_URL = "https://www.deervalley.com"
SOURCE_NAME = "Deer Valley Resort"

# Approximate coordinates for Deer Valley locations (so the radius filter works
# and so the venue page can link them up properly).
LOCATION_COORDS = {
    "snow park base area": (40.6374, -111.4783),
    "snow park outdoor amphitheater": (40.6374, -111.4783),
    "silver lake base area": (40.6155, -111.4858),
    "historic park city main street": (40.6453, -111.4977),
    "on mountain": (40.6285, -111.4820),  # approximate mid-mountain
}


def scrape_deer_valley():
    """Fetch and parse Deer Valley's events. Returns a list of event dicts."""
    print("Scraping Deer Valley Resort events...")
    events = []

    try:
        raw_events = _fetch_and_parse_html()
    except Exception as ex:
        print(f"  Error fetching Deer Valley events: {ex}")
        return []

    print(f"  Got {len(raw_events)} raw events from Deer Valley")

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
        # Dedup by (title, date)
        key = (parsed["title"].lower().strip()[:40], parsed["date"][:10])
        if key in seen:
            continue
        seen.add(key)
        events.append(parsed)

    print(f"  Returning {len(events)} clean events ({dropped_past} past dropped)")
    return events


def _fetch_and_parse_html():
    """Get the events page, extract the JSON-in-HTML, decode and return list."""
    r = requests.get(EVENTS_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
    r.raise_for_status()

    # The events live inside <var class="results hidden">[...]</var>
    # The contents are HTML-entity encoded so we can't use a simple regex on raw quotes.
    m = re.search(
        r'<var[^>]*class="results[^"]*"[^>]*>\s*(.*?)\s*</var>',
        r.text,
        re.DOTALL,
    )
    if not m:
        raise Exception("Could not find <var class='results'> block in HTML")

    encoded = m.group(1).strip()
    # HTML-decode: &quot; -> ", &#39; -> ', &amp; -> &, etc.
    decoded = html.unescape(encoded)

    return json.loads(decoded)


def _parse_event(raw):
    """Convert one raw Deer Valley event dict to our standard schema."""
    try:
        title = (raw.get("name") or "").strip()
        if not title or len(title) < 3:
            return None

        # Date and time from startDateDateTime: "2026-07-17T18:00:00"
        start_str = raw.get("startDateDateTime") or ""
        end_str = raw.get("endDateDateTime") or ""
        all_day = bool(raw.get("allDay"))

        if not start_str:
            return None

        try:
            start_dt = datetime.fromisoformat(start_str)
        except Exception:
            return None

        date_iso = start_dt.strftime("%Y-%m-%d")
        start_time = None if all_day else start_dt.strftime("%-I:%M %p")

        end_time = None
        end_date_iso = None
        if end_str:
            try:
                end_dt = datetime.fromisoformat(end_str)
                end_date_iso = end_dt.strftime("%Y-%m-%d")
                if not all_day:
                    end_time = end_dt.strftime("%-I:%M %p")
            except Exception:
                pass

        # Subtitle = tagline (often more useful than the full description)
        # Description = full HTML body (we strip tags)
        subtitle = (raw.get("subtitle") or "").strip()
        desc_html = raw.get("description") or ""
        desc_text = re.sub(r"<[^>]+>", " ", desc_html)
        desc_text = re.sub(r"\s+", " ", desc_text).strip()
        description = subtitle if subtitle else desc_text[:300]
        if subtitle and desc_text:
            # Combine if we have both
            description = (subtitle + " — " + desc_text)[:300]

        # Location: first item in locations array
        locations = raw.get("locations") or []
        loc_name = ""
        lat, lng = None, None
        if locations and isinstance(locations[0], dict):
            loc_name = locations[0].get("displayName") or locations[0].get("name") or ""
            # Look up coords
            coords = LOCATION_COORDS.get(loc_name.lower())
            if coords:
                lat, lng = coords

        location = f"{loc_name}, Deer Valley, Park City, UT" if loc_name else "Deer Valley, Park City, UT"

        # Categories (skip "Community and Local" — too generic)
        types = raw.get("types") or []
        categories = []
        for t in types:
            name = (t.get("displayName") or t.get("name") or "") if isinstance(t, dict) else ""
            if name and "community" not in name.lower():
                categories.append(name)

        # Link — relative URL on deervalley.com
        target = (raw.get("targetUrl") or "").strip()
        link = f"{BASE_URL}{target}" if target.startswith("/") else target
        if not link:
            link = EVENTS_URL

        # Recurrence
        recurrence = raw.get("recurrence")

        event = {
            "title": title,
            "date": date_iso,
            "description": description,
            "location": location,
            "link": link,
            "source": SOURCE_NAME,
            "source_url": EVENTS_URL,
        }
        if start_time:
            event["start_time"] = start_time
        if end_time:
            event["end_time"] = end_time
        if end_date_iso and end_date_iso != date_iso:
            event["end_date"] = end_date_iso
        if lat is not None:
            event["lat"] = lat
        if lng is not None:
            event["lng"] = lng
        if categories:
            event["categories"] = categories
        if recurrence:
            event["recurrence_label"] = recurrence  # informational; not used by dedup

        return event

    except Exception as ex:
        # Defensive — never let one bad event kill the run
        return None


if __name__ == "__main__":
    # Stand-alone test
    results = scrape_deer_valley()
    print(f"\nTotal: {len(results)} events")
    print()
    for e in results[:10]:
        time_s = e.get("start_time", "(all day)")
        cats = ",".join(e.get("categories", [])) or "-"
        print(f"  {e['date']} {time_s:>10s} | {e['title'][:55]:55s} | {cats[:25]:25s} | @ {e.get('location','?')[:40]}")

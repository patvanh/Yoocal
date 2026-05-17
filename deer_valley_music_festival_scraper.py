"""
Deer Valley Music Festival scraper.

DVMF (deervalleymusicfestival.org) is Utah Symphony's summer concert
series at Snow Park Outdoor Amphitheater and St. Mary's Catholic Church
in Park City. Headliners include Lyle Lovett, Chris Botti, Idina Menzel,
plus classical programs.

Their /schedule/ page embeds Schema.org MusicEvent JSON-LD blocks — one
per concert. Clean parseable data, no auth needed.

Each MusicEvent has:
    name           — concert title (with smart quotes — decode HTML entities)
    startDate      — "2026-07-17T20:00" (ISO datetime, no timezone — Mountain Time)
    endDate        — sometimes date-only "2026-07-17", sometimes datetime
    location.name  — "Snow Park Outdoor Amphitheater" or "St. Mary's Catholic Church"
    location.address — full street address
    description    — HTML-encoded text (has &rsquo;, &ldquo;, &mdash; etc)
    image          — concert image URL
    performer.name — "Deer Valley® Music Festival"

Public entry point:
    scrape_deer_valley_music_festival() -> list of event dicts
"""

import requests
import re
import json
import html
from datetime import datetime

URL = "https://deervalleymusicfestival.org/schedule/"
SOURCE_NAME = "Deer Valley Music Festival"
SOURCE_URL = "https://deervalleymusicfestival.org/schedule/"

# Known DVMF venues with their lat/lng
# Snow Park Outdoor Amphitheater is the main outdoor stage at Deer Valley base
# St. Mary's Catholic Church is the chamber music venue
VENUE_COORDS = {
    "snow park outdoor amphitheater": (40.6294, -111.4884),
    "st. mary's catholic church":     (40.6889, -111.5197),
    "st mary's catholic church":      (40.6889, -111.5197),
}
DEFAULT_LAT, DEFAULT_LNG = 40.6461, -111.4980  # Park City fallback


def scrape_deer_valley_music_festival():
    """Fetch + parse DVMF schedule into yoocal-shaped event dicts."""
    print(f"Scraping Deer Valley Music Festival...")
    try:
        raw_events = _fetch_events()
    except Exception as ex:
        print(f"  Error: {ex}")
        return []

    today_iso = datetime.now().strftime("%Y-%m-%d")
    out = []
    dropped_past = 0

    for raw in raw_events:
        parsed = _parse_event(raw)
        if not parsed:
            continue
        if parsed["date"] < today_iso:
            dropped_past += 1
            continue
        out.append(parsed)

    print(f"  Got {len(raw_events)} raw events, returning {len(out)} ({dropped_past} past dropped)")
    return out


def _fetch_events():
    """Pull all MusicEvent JSON-LD blocks from the schedule page."""
    r = requests.get(
        URL,
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh) Chrome/124.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
        timeout=20,
    )
    r.raise_for_status()
    text = r.text

    # Pull each <script type="application/ld+json"> block
    ld_blocks = re.findall(
        r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        text,
        re.DOTALL,
    )

    music_events = []
    for block in ld_blocks:
        if '"MusicEvent"' not in block:
            continue
        # Clean control characters (raw newlines inside string literals break JSON parsing)
        cleaned = _clean_json_block(block)
        try:
            data = json.loads(cleaned)
        except Exception:
            # Fallback: extract fields with regex if JSON won't parse
            data = _regex_extract_event(block)
            if not data:
                continue
        if data.get("@type") == "MusicEvent":
            music_events.append(data)

    return music_events


def _clean_json_block(s):
    """Strip raw control chars inside JSON string values."""
    # The site emits literal \n inside description strings (invalid JSON).
    # Replace any raw \n, \r, \t inside string contexts with spaces.
    # Simple heuristic: replace these chars globally — JSON keys never contain them.
    return s.strip().replace("\n", " ").replace("\r", " ").replace("\t", " ")


def _regex_extract_event(block):
    """Fallback: pull fields out of an unparseable MusicEvent block."""
    out = {"@type": "MusicEvent"}

    m = re.search(r'"name"\s*:\s*"([^"]+)"', block)
    if m:
        out["name"] = m.group(1)

    m = re.search(r'"startDate"\s*:\s*"([^"]+)"', block)
    if m:
        out["startDate"] = m.group(1)

    m = re.search(r'"endDate"\s*:\s*"([^"]+)"', block)
    if m:
        out["endDate"] = m.group(1)

    # Location is nested
    venue_m = re.search(r'"location"\s*:\s*\{[^}]*"name"\s*:\s*"([^"]+)"[^}]*"address"\s*:\s*"([^"]+)"', block, re.DOTALL)
    if venue_m:
        out["location"] = {"name": venue_m.group(1), "address": venue_m.group(2)}

    # Description: greedy match between "description":" and the next "," at the top level
    desc_m = re.search(r'"description"\s*:\s*"([^"]+(?:\\.[^"]*)*)"', block, re.DOTALL)
    if desc_m:
        out["description"] = desc_m.group(1)

    m = re.search(r'"image"\s*:\s*"([^"]+)"', block)
    if m:
        out["image"] = m.group(1)

    return out if out.get("name") and out.get("startDate") else None


def _parse_event(raw):
    """Convert one MusicEvent dict to our standard schema."""
    try:
        # Title — decode HTML entities
        name = (raw.get("name") or "").strip()
        if not name or len(name) < 3:
            return None
        title = html.unescape(name)

        # Date / time
        start_str = raw.get("startDate") or ""
        # Format: "2026-07-17T20:00" or "2026-07-17"
        if "T" in start_str:
            try:
                start_dt = datetime.strptime(start_str, "%Y-%m-%dT%H:%M")
            except ValueError:
                try:
                    start_dt = datetime.strptime(start_str, "%Y-%m-%dT%H:%M:%S")
                except ValueError:
                    return None
            date_iso = start_dt.strftime("%Y-%m-%d")
            start_time = start_dt.strftime("%-I:%M %p")
        else:
            # Date only
            try:
                start_dt = datetime.strptime(start_str, "%Y-%m-%d")
            except ValueError:
                return None
            date_iso = start_str
            start_time = None

        # End time (most events are date-only end, no useful end_time)
        end_str = raw.get("endDate") or ""
        end_time = None
        end_date_iso = None
        if "T" in end_str:
            try:
                end_dt = datetime.strptime(end_str, "%Y-%m-%dT%H:%M")
                if end_dt.strftime("%Y-%m-%d") != date_iso:
                    end_date_iso = end_dt.strftime("%Y-%m-%d")
                if start_time:
                    end_time = end_dt.strftime("%-I:%M %p")
            except ValueError:
                pass
        elif end_str and end_str != date_iso:
            end_date_iso = end_str

        # Location
        loc_obj = raw.get("location") or {}
        venue_name = (loc_obj.get("name") or "").strip()
        venue_address = (loc_obj.get("address") or "").strip()

        if venue_address:
            location = f"{venue_name}, {venue_address}" if venue_name else venue_address
        elif venue_name:
            location = f"{venue_name}, Park City, UT"
        else:
            location = "Park City, UT"

        # Coordinates per venue
        lat, lng = DEFAULT_LAT, DEFAULT_LNG
        venue_key = venue_name.lower().strip()
        if venue_key in VENUE_COORDS:
            lat, lng = VENUE_COORDS[venue_key]

        # Description — decode HTML entities, strip tags
        desc_raw = raw.get("description") or ""
        description = html.unescape(desc_raw)
        description = re.sub(r"<[^>]+>", " ", description)
        description = re.sub(r"\s+", " ", description).strip()
        if len(description) > 600:
            description = description[:597] + "..."
        if not description:
            description = f"Deer Valley Music Festival concert at {venue_name}."

        # Image
        image_url = (raw.get("image") or "").strip() or None

        event = {
            "title": title,
            "date": date_iso,
            "description": description,
            "location": location,
            "link": SOURCE_URL,
            "source": SOURCE_NAME,
            "source_url": SOURCE_URL,
            "lat": lat,
            "lng": lng,
            "categories": ["Music", "Concert"],
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
    events = scrape_deer_valley_music_festival()
    print(f"\nTotal: {len(events)} events\n")
    for e in events:
        time_s = e.get("start_time", "(all day)")
        loc_short = e["location"].split(",")[0][:40]
        print(f"  {e['date']} {time_s:>9s} | {e['title'][:45]:45s} | {loc_short}")

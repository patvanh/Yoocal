"""
Universal Schema.org Event scraper.

Many event sites embed Schema.org Event data as JSON-LD <script> blocks
in their HTML. This includes:
  - WordPress sites with The Events Calendar plugin (tribe-events)
  - Music festivals (DVMF used MusicEvent)
  - Showpass / Eventbrite event pages
  - Many CMS-generated event detail pages

This scraper takes a URL, fetches the HTML, finds all JSON-LD blocks
with @type in {Event, MusicEvent, TheaterEvent, SportsEvent, Festival,
ScreeningEvent, ComedyEvent, etc.}, and converts them to yoocal events.

Public API:
    scrape_schema_org_events(url, *, source_name=None, default_lat=None,
                              default_lng=None, default_categories=None,
                              max_events=200) -> list of event dicts

    scrape_schema_org_sources(sources_config) -> list of event dicts
        sources_config is a list of dicts, each:
            {"url": "...", "source_name": "...", "default_lat": ..., ...}

Recognized event types (all converted to yoocal events):
    Event, MusicEvent, TheaterEvent, SportsEvent, BusinessEvent,
    ChildrensEvent, ComedyEvent, CourseInstance, DanceEvent,
    DeliveryEvent, EducationEvent, ExhibitionEvent, Festival,
    FoodEvent, LiteraryEvent, PublicationEvent, SaleEvent,
    ScreeningEvent, SocialEvent, VisualArtsEvent
"""

import re
import json
import html
from datetime import datetime
from urllib.parse import urljoin, urlparse

import requests

# Event types we recognize as actual events
EVENT_TYPES = {
    "Event", "MusicEvent", "TheaterEvent", "SportsEvent", "BusinessEvent",
    "ChildrensEvent", "ComedyEvent", "DanceEvent", "EducationEvent",
    "ExhibitionEvent", "Festival", "FoodEvent", "LiteraryEvent",
    "ScreeningEvent", "SocialEvent", "VisualArtsEvent",
}

# Common HTTP headers
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


# --------------------------------------------------------------
# Public API
# --------------------------------------------------------------

def _human_to_iso_datetime(s):
    """Convert a human datetime like 'Jul 16, 2026 08:30 PM' to ISO
    '2026-07-16T20:30', or '' if unparseable."""
    if not s:
        return ""
    s = s.strip()
    if re.match(r"\d{4}-\d{2}-\d{2}", s):
        return s
    fmts = [
        "%b %d, %Y %I:%M %p", "%B %d, %Y %I:%M %p",
        "%b %d, %Y %I:%M%p", "%B %d, %Y %I:%M%p",
        "%b %d, %Y", "%B %d, %Y",
        "%m/%d/%Y %I:%M %p", "%m/%d/%Y",
    ]
    for fmt in fmts:
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%dT%H:%M")
        except ValueError:
            continue
    return ""


def _fallback_event_from_html(html_text, url):
    """No Event JSON-LD -> synthesize a raw Event dict from a datetime attr
    (date) + page title/H1 (name) so _parse_event can handle it. Or None."""
    if not html_text:
        return None
    iso = ""
    for raw_dt in re.findall(r'datetime=["\']([^"\']+)["\']', html_text):
        iso = _human_to_iso_datetime(raw_dt)
        if iso:
            break
    if not iso:
        return None
    title = ""
    mh1 = re.search(r"<h1[^>]*>(.*?)</h1>", html_text, re.DOTALL | re.IGNORECASE)
    if mh1:
        title = re.sub(r"<[^>]+>", "", mh1.group(1))
    if not title or len(title.strip()) < 3:
        mt = re.search(r"<title[^>]*>(.*?)</title>", html_text, re.DOTALL | re.IGNORECASE)
        if mt:
            title = mt.group(1)
    title = html.unescape(title or "").strip()
    title = re.split(r"\s+[|\u2013-]\s+", title)[0].strip()
    if not title or len(title) < 3:
        return None
    return {"@type": "Event", "name": title, "startDate": iso}


def scrape_schema_org_events(
    url,
    source_name=None,
    default_lat=None,
    default_lng=None,
    default_categories=None,
    default_city=None,
    max_events=200,
    timeout=20,
):
    """
    Extract Schema.org Event JSON-LD from a URL and return yoocal events.

    Args:
        url: The page URL to scrape
        source_name: Override for "source" field. Defaults to URL hostname.
        default_lat / default_lng: Coordinates if event location can't be geocoded
        default_categories: List of category strings to apply
        default_city: City name used in location string fallback
        max_events: Cap number of events returned
        timeout: HTTP timeout in seconds

    Returns:
        List of event dicts in yoocal schema format
    """
    if not source_name:
        source_name = urlparse(url).netloc.replace("www.", "")

    try:
        html_text = _fetch(url, timeout=timeout)
    except Exception as ex:
        print(f"  [{source_name}] fetch failed: {ex}")
        return []

    raw_events = _extract_schema_events(html_text)
    if not raw_events:
        fb = _fallback_event_from_html(html_text, url)
        if fb:
            raw_events = [fb]
        else:
            print(f"  [{source_name}] no Schema.org Event JSON-LD or datetime attr")
            return []

    today_iso = datetime.now().strftime("%Y-%m-%d")
    out = []
    seen_keys = set()
    dropped_past = 0
    dropped_unparseable = 0

    for raw in raw_events:
        parsed = _parse_event(
            raw,
            source_name=source_name,
            source_url=url,
            default_lat=default_lat,
            default_lng=default_lng,
            default_categories=default_categories or ["Event"],
            default_city=default_city,
        )
        if not parsed:
            dropped_unparseable += 1
            continue
        # Keep event if either start OR end date is today/future
        eff_end = parsed.get("end_date") or parsed["date"]
        if eff_end < today_iso:
            dropped_past += 1
            continue
        # If start is past but end is future, bump date forward to today
        # so the event shows up on current+future days
        if parsed["date"] < today_iso <= eff_end:
            parsed["date"] = today_iso

        # If JSON-LD didn't supply start_time, try to extract from visible HTML
        if not parsed.get("start_time"):
            st, et = _extract_time_from_html(html_text)
            if st:
                parsed["start_time"] = st
                if et:
                    parsed["end_time"] = et

        # Dedup within this page
        key = (parsed["title"][:40].lower(), parsed["date"])
        if key in seen_keys:
            continue
        seen_keys.add(key)

        out.append(parsed)
        if len(out) >= max_events:
            break

    print(f"  [{source_name}] {len(out)} events ({dropped_past} past, {dropped_unparseable} unparseable, "
          f"{len(raw_events) - len(out) - dropped_past - dropped_unparseable} dupes)")
    return out


def scrape_schema_org_sources(sources_config):
    """
    Run scrape_schema_org_events for each entry in a config list.

    sources_config example:
        [
            {"url": "https://deervalleymusicfestival.org/schedule/",
             "source_name": "Deer Valley Music Festival",
             "default_lat": 40.6294, "default_lng": -111.4884,
             "default_categories": ["Music", "Concert"],
             "default_city": "Park City, UT"},
            {"url": "https://gtmf.org/experience/season65",
             "source_name": "Grand Teton Music Festival",
             ...},
        ]
    """
    all_events = []
    for cfg in sources_config:
        url = cfg.get("url")
        if not url:
            continue
        events = scrape_schema_org_events(
            url=url,
            source_name=cfg.get("source_name"),
            default_lat=cfg.get("default_lat"),
            default_lng=cfg.get("default_lng"),
            default_categories=cfg.get("default_categories"),
            default_city=cfg.get("default_city"),
        )
        all_events.extend(events)
    return all_events


# --------------------------------------------------------------
# Internals
# --------------------------------------------------------------

def _fetch(url, timeout=20):
    r = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout, allow_redirects=True)
    r.raise_for_status()
    return r.text


def _extract_schema_events(html_text):
    """Find all JSON-LD blocks and return any Event-typed objects."""
    blocks = re.findall(
        r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html_text,
        re.DOTALL,
    )
    events = []
    for block in blocks:
        events.extend(_find_events_in_block(block))
    return events


def _find_events_in_block(block):
    """Walk a JSON-LD block (which may have @graph, nested objects, or top-level Event)."""
    found = []

    # Strip raw control characters that break JSON parsing
    cleaned = block.strip().replace("\n", " ").replace("\r", " ").replace("\t", " ")

    try:
        data = json.loads(cleaned)
    except Exception:
        # Try regex fallback
        return _regex_extract_events(block)

    items = data if isinstance(data, list) else [data]
    for item in items:
        if not isinstance(item, dict):
            continue
        # Sometimes @graph contains the actual list
        graph = item.get("@graph")
        if isinstance(graph, list):
            for g in graph:
                if isinstance(g, dict) and _is_event_type(g.get("@type")):
                    found.append(g)
        # ItemList of events (race aggregators, listing pages): events are
        # nested under itemListElement[].item as Event/SportsEvent objects.
        if item.get("@type") == "ItemList":
            for li in item.get("itemListElement", []):
                if not isinstance(li, dict):
                    continue
                inner = li.get("item")
                if isinstance(inner, dict) and _is_event_type(inner.get("@type")):
                    found.append(inner)
        if _is_event_type(item.get("@type")):
            found.append(item)

    return found


def _is_event_type(t):
    if not t:
        return False
    if isinstance(t, list):
        return any(_is_event_type(x) for x in t)
    if isinstance(t, str):
        return t in EVENT_TYPES
    return False


def _regex_extract_events(block):
    """When JSON parsing fails, try to pull individual Event fields via regex.

    This is a best-effort fallback for pages where the JSON-LD has minor
    invalid syntax (newlines in strings, smart quotes, etc).
    """
    out = []
    # Find @type values that look like Events
    type_re = re.compile(r'"@type"\s*:\s*"(MusicEvent|TheaterEvent|SportsEvent|Festival|ScreeningEvent|ExhibitionEvent|Event)"')
    if not type_re.search(block):
        return []

    # Crude approach: split the block by "@type" occurrences and parse each chunk
    chunks = re.split(r'(?="@type"\s*:\s*"(?:Music|Theater|Sports|Festival|Screening|Exhibition|)?Event")', block)
    for chunk in chunks:
        if not type_re.search(chunk):
            continue
        ev = {}
        m = re.search(r'"@type"\s*:\s*"([^"]+)"', chunk)
        if m: ev["@type"] = m.group(1)
        m = re.search(r'"name"\s*:\s*"([^"]+)"', chunk)
        if m: ev["name"] = m.group(1)
        m = re.search(r'"startDate"\s*:\s*"([^"]+)"', chunk)
        if m: ev["startDate"] = m.group(1)
        m = re.search(r'"endDate"\s*:\s*"([^"]+)"', chunk)
        if m: ev["endDate"] = m.group(1)
        m = re.search(r'"description"\s*:\s*"((?:\\.|[^"\\])*)"', chunk, re.DOTALL)
        if m: ev["description"] = m.group(1)
        m = re.search(r'"url"\s*:\s*"([^"]+)"', chunk)
        if m: ev["url"] = m.group(1)
        m = re.search(r'"image"\s*:\s*"([^"]+)"', chunk)
        if m: ev["image"] = m.group(1)
        # Location nested
        loc_m = re.search(
            r'"location"\s*:\s*\{[^}]*"name"\s*:\s*"([^"]+)"(?:[^}]*"address"\s*:\s*"([^"]+)")?',
            chunk,
            re.DOTALL,
        )
        if loc_m:
            ev["location"] = {"name": loc_m.group(1)}
            if loc_m.group(2):
                ev["location"]["address"] = loc_m.group(2)

        if ev.get("name") and ev.get("startDate") and ev.get("@type"):
            out.append(ev)
    return out




# HTML time-extraction fallback for sites whose Schema.org JSON-LD has
# date-only fields (e.g. visitparkcity.com Simpleview pages) but visible
# HTML shows times like "Time: 9:00 AM to 10:30 AM".
_TIME_RE = re.compile(
    r"(\d{1,2}:\d{2}\s*[AaPp][Mm])"          # captures 9:00 AM
    r"(?:\s*(?:to|\u2013|\u2014|-|\u2010|&ndash;|&#8211;)\s*"  # to / dash / en-dash
    r"(\d{1,2}:\d{2}\s*[AaPp][Mm]))?",        # optional end time
    re.IGNORECASE,
)


def _extract_time_from_html(html_text):
    """
    Look for time-range patterns in visible HTML.
    Returns (start_time, end_time) or (None, None).
    """
    if not html_text:
        return None, None

    # Strip tags so labels and times are contiguous
    text = re.sub(r"<[^>]+>", " ", html_text)
    text = re.sub(r"\s+", " ", text)

    # Look for the FIRST time-range pattern in the visible body.
    # Pattern: "9:00 AM to 10:30 AM", "9:00 AM - 10:30 AM",
    # "9:00 AM \u2013 10:30 AM" (en-dash), "9:00 AM \u2014 10:30 AM" (em-dash).
    range_re = re.compile(
        r"(\d{1,2}:\d{2}\s*[AaPp][Mm])"
        r"\s*(?:to|\u2013|\u2014|-|&ndash;|&#8211;)\s*"
        r"(\d{1,2}:\d{2}\s*[AaPp][Mm])",
        re.IGNORECASE,
    )
    m = range_re.search(text)
    if m:
        s = _normalize_time(m.group(1))
        e = _normalize_time(m.group(2))
        if s:
            return s, e

    # If no range, fall back to first standalone time
    single_re = re.compile(r"(\d{1,2}:\d{2}\s*[AaPp][Mm])", re.IGNORECASE)
    m = single_re.search(text)
    if m:
        s = _normalize_time(m.group(1))
        if s:
            return s, None

    return None, None

def _normalize_time(s):
    """Normalize '9:00 am' -> '9:00 AM'. Returns None if unparseable."""
    if not s:
        return None
    s = s.strip().upper().replace(".", "")
    s = re.sub(r"\s+", " ", s)
    # Ensure space before AM/PM
    s = re.sub(r"([0-9])([AP]M)", r"\1 \2", s)
    return s if re.match(r"^\d{1,2}:\d{2} [AP]M$", s) else None


def _parse_event(raw, source_name, source_url, default_lat, default_lng,
                 default_categories, default_city):
    """Convert one Schema.org Event dict to a yoocal event dict."""
    try:
        # Title
        name = (raw.get("name") or "").strip()
        if isinstance(name, dict):
            name = (name.get("@value") or "").strip()
        if not name or len(name) < 3:
            return None
        # Decode entities FIRST so HTML-encoded tags like &lt;em&gt;
        # become literal <em> tags, THEN strip them. Some sources (e.g.
        # National Museum of Wildlife Art) double-encode their titles, so
        # the order matters — stripping before decode misses everything.
        title = html.unescape(name)
        title = re.sub(r"<[^>]+>", "", title)
        title = re.sub(r"\s+", " ", title).strip()

        # Date/time — Schema.org gives "2026-07-17T20:00" or "2026-07-17"
        start_str = raw.get("startDate") or ""
        if isinstance(start_str, dict):
            start_str = start_str.get("@value") or ""
        start_str = start_str.strip()

        date_iso, start_time = _parse_iso_datetime(start_str)
        if not date_iso:
            return None

        # End
        end_str = (raw.get("endDate") or "").strip() if isinstance(raw.get("endDate"), str) else ""
        end_date_iso, end_time = _parse_iso_datetime(end_str) if end_str else (None, None)
        if end_date_iso == date_iso:
            end_date_iso = None  # same day, not a multi-day event

        # Location
        loc_obj = raw.get("location") or {}
        if isinstance(loc_obj, list):
            loc_obj = loc_obj[0] if loc_obj else {}
        venue_name = ""
        venue_address = ""
        if isinstance(loc_obj, dict):
            venue_name = (loc_obj.get("name") or "").strip()
            addr = loc_obj.get("address")
            if isinstance(addr, str):
                venue_address = addr.strip()
            elif isinstance(addr, dict):
                # Schema.org PostalAddress
                parts = [addr.get(k, "") for k in ("streetAddress", "addressLocality", "addressRegion", "postalCode")]
                venue_address = ", ".join(p for p in parts if p)
        elif isinstance(loc_obj, str):
            venue_address = loc_obj.strip()

        if venue_address and venue_name:
            location = f"{venue_name}, {venue_address}"
        elif venue_name:
            location = f"{venue_name}, {default_city}" if default_city else venue_name
        elif venue_address:
            location = venue_address
        elif default_city:
            location = default_city
        else:
            location = "Location TBD"

        # Description — decode HTML entities, strip tags
        desc_raw = raw.get("description") or ""
        if isinstance(desc_raw, list):
            desc_raw = desc_raw[0] if desc_raw else ""
        description = html.unescape(str(desc_raw))
        description = re.sub(r"<[^>]+>", " ", description)
        description = re.sub(r"\s+", " ", description).strip()
        if len(description) > 2000:
            description = description[:1997] + "..."
        if not description:
            description = title

        # Link
        link = raw.get("url") or source_url
        if isinstance(link, list):
            link = link[0] if link else source_url
        if link and not link.startswith("http"):
            link = urljoin(source_url, link)

        # Image
        image_url = raw.get("image") or ""
        if isinstance(image_url, list):
            image_url = image_url[0] if image_url else ""
        if isinstance(image_url, dict):
            image_url = image_url.get("url") or image_url.get("contentUrl") or ""

        # Categories — start with default, add type hints
        categories = list(default_categories) if default_categories else ["Event"]
        ev_type = raw.get("@type")
        if isinstance(ev_type, str):
            type_categories = {
                "MusicEvent": ["Music"],
                "TheaterEvent": ["Theater"],
                "SportsEvent": ["Sports"],
                "ComedyEvent": ["Comedy"],
                "ScreeningEvent": ["Film"],
                "Festival": ["Festival"],
                "DanceEvent": ["Dance"],
                "ExhibitionEvent": ["Art", "Exhibition"],
                "FoodEvent": ["Food"],
                "EducationEvent": ["Education"],
                "ChildrensEvent": ["Family"],
            }.get(ev_type)
            if type_categories:
                categories = type_categories

        event = {
            "title": title,
            "date": date_iso,
            "description": description,
            "location": location,
            "link": link,
            "source": source_name,
            "source_url": source_url,
            "lat": default_lat if default_lat is not None else 0,
            "lng": default_lng if default_lng is not None else 0,
            "categories": categories,
        }
        # Don't keep orphan end_time with no start_time (looks broken in UI)
        if end_time and not start_time:
            end_time = None

        if start_time:
            event["start_time"] = start_time
        if end_time:
            event["end_time"] = end_time
        if end_date_iso:
            event["end_date"] = end_date_iso
        if image_url:
            event["image_url"] = image_url
        if venue_address:
            event["address"] = venue_address
        if venue_name:
            event["venue_name"] = venue_name

        return event

    except Exception:
        return None


def _parse_iso_datetime(s):
    """Parse an ISO 8601 datetime/date string. Returns (date_iso, start_time) or (None, None)."""
    if not s:
        return None, None
    s = s.strip()
    # Strip timezone suffix if present (we lose tz info but that's ok for our display)
    s_no_tz = re.sub(r"([+-]\d{2}:?\d{2}|Z)$", "", s)

    formats = [
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(s_no_tz, fmt)
            date_iso = dt.strftime("%Y-%m-%d")
            if "%H" in fmt:
                start_time = dt.strftime("%-I:%M %p")
            else:
                start_time = None
            return date_iso, start_time
        except ValueError:
            continue
    # Fallback — try just the date prefix
    m = re.match(r"^(\d{4}-\d{2}-\d{2})", s_no_tz)
    if m:
        return m.group(1), None
    return None, None


# --------------------------------------------------------------
# CLI
# --------------------------------------------------------------

if __name__ == "__main__":
    import sys
    import argparse

    parser = argparse.ArgumentParser(description="Test the universal Schema.org Event parser on a URL.")
    parser.add_argument("--url", required=True, help="URL to scrape")
    parser.add_argument("--source", default=None, help="Override source name")
    parser.add_argument("--city", default=None, help="Default city for location fallback")
    args = parser.parse_args()

    events = scrape_schema_org_events(
        url=args.url,
        source_name=args.source,
        default_city=args.city,
    )
    print(f"\n{len(events)} events parsed:\n")
    for e in events:
        time_s = e.get("start_time", "(all day)")
        cats = ",".join(e.get("categories", []))[:30]
        loc_short = e["location"].split(",")[0][:40]
        print(f"  {e['date']} {time_s:>9s} | {e['title'][:45]:45s} | {cats:20s} | {loc_short}")

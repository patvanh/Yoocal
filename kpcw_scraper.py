"""
KPCW Community Calendar scraper.

KPCW (Park City public radio) uses the Tockify calendar service. Their
public-facing iframe at https://www.kpcw.org/kpcw-community-calendar embeds
https://tockify.com/kpcwcommunitycalendar — which is itself backed by a
JSON API at https://tockify.com/api/ngevent.

We hit that API directly. No HTML scraping needed. The API returns up to
200 events per call, with rich structured data including:
  - title, description
  - start/end times in epoch milliseconds (America/Denver)
  - venue name + street address
  - lat/lng
  - category tags (Art, Music, Education, Sports/Recreation, etc.)
  - custom RSVP/ticket link

KPCW covers BOTH Summit County (Park City) AND Wasatch County (Heber Valley),
so this scraper produces TWO event lists — one for each city — using the
event's location to route it.

Public entry point:
    scrape_kpcw_calendar() -> (parkcity_events: list, heber_events: list)

Routing logic:
- Events with addresses containing Heber Valley keywords go to Heber
- Everything else (or events with no address) goes to Park City
  (KPCW is primarily Park City focused so PC is the safer default)
"""

import re
import json
import requests
from datetime import datetime, timedelta, timezone

CALENDAR_NAME = "kpcwcommunitycalendar"
API_URL = "https://tockify.com/api/ngevent"
SOURCE_NAME = "KPCW Community Calendar"
SOURCE_URL = "https://www.kpcw.org/kpcw-community-calendar"

# Same keyword list as scraper.py's HEBER_VENUE_KEYWORDS — kept local so this
# module is standalone, but stays consistent with the rest of the pipeline.
HEBER_KEYWORDS = [
    "heber valley", "soldier hollow", "heber city", "midway, ut",
    "midway town", "wallsburg", "deer creek state park", "kamas",
    "midway,", "heber,", "kamas,",
]


import re as _re_kpcw

# Promotional billboard detection: KPCW's Tockify feed repeats a single
# event/announcement across many days as a countdown "billboard". We collapse
# those to a single card while preserving genuinely recurring events.
_PROMO_PHRASES = [
    "register now", "registration open", "applications open", "apply now",
    "grand opening", "now available", "sign up", "sign-up", "tickets now",
    "save the date", "coming soon", "on sale now", "tryouts", "open now",
]
# "Every Monday", "Every Thursday", etc. mark legitimately recurring events.
_RECURRING_RE = _re_kpcw.compile(r"\bevery\s+(mon|tue|wed|thu|fri|sat|sun)", _re_kpcw.I)
# A date span in the title ("June 12-14", "May 23 and 24") marks a billboard.
_DATE_IN_TITLE_RE = _re_kpcw.compile(
    r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{1,2}",
    _re_kpcw.I,
)


_MONTHS_KPCW = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def _date_from_title(title, fallback_iso):
    """If the title contains an explicit month+day, return that as YYYY-MM-DD.

    Uses the year from fallback_iso (the billboard's shown date) and rolls to
    the next year only if the resulting date would be more than ~1 month in the
    past relative to the fallback. Returns fallback_iso when no date is found.
    """
    m = _re_kpcw.search(
        r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+(\d{1,2})",
        title, _re_kpcw.I,
    )
    if not m:
        return fallback_iso
    mon = _MONTHS_KPCW.get(m.group(1).lower()[:3])
    day = int(m.group(2))
    if not mon or not (1 <= day <= 31):
        return fallback_iso
    try:
        fb_year = int(fallback_iso[:4])
        candidate = f"{fb_year:04d}-{mon:02d}-{day:02d}"
    except (ValueError, TypeError):
        return fallback_iso
    # Only override if the parsed date is on/after the shown date — i.e. the
    # title is announcing a future event. Never move an event earlier.
    if candidate >= fallback_iso:
        return candidate
    # Parsed date is earlier in the same year; the event likely refers to next
    # year only if the gap is large. Keep fallback to stay conservative.
    return fallback_iso


def _date_from_text(text, fallback_iso, today_iso):
    """Scan free text (description) for an explicit date like
    'Sunday, May 31, 2026' or 'Monday, June 8'. Returns YYYY-MM-DD if a single
    confident future date is found, else fallback_iso.

    Conservative: only overrides when the API date is unreliable (equals today)
    and the text names exactly one clear date. Prefers a date >= today.
    """
    if not text:
        return fallback_iso
    # Match "Month DD, YYYY" or "Month DD" (optionally preceded by a weekday).
    pat = _re_kpcw.compile(
        r"(?:(?:mon|tue|wed|thu|fri|sat|sun)[a-z]*,?\s+)?"
        r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+"
        r"(\d{1,2})(?:st|nd|rd|th)?(?:,?\s+(\d{4}))?",
        _re_kpcw.I,
    )
    found = []
    for m in pat.finditer(text):
        mon = _MONTHS_KPCW.get(m.group(1).lower()[:3])
        if not mon:
            continue
        day = int(m.group(2))
        if not (1 <= day <= 31):
            continue
        year = int(m.group(3)) if m.group(3) else int(fallback_iso[:4])
        cand = f"{year:04d}-{mon:02d}-{day:02d}"
        found.append(cand)
    if not found:
        return fallback_iso
    # Prefer future dates (on/after today). De-dupe.
    future = sorted(set(d for d in found if d >= today_iso))
    if len(future) == 1:
        return future[0]
    # If multiple distinct future dates, it's ambiguous (e.g. "tickets May 20,
    # event June 8") — don't guess. Keep fallback.
    return fallback_iso


def _collapse_billboards(events):
    """Collapse promotional multi-day billboards to a single (earliest) card.

    Recurring events whose titles say "Every <weekday>" are preserved in full.
    """
    by_title = {}
    for e in events:
        by_title.setdefault(e.get("title", "").strip(), []).append(e)

    out = []
    for title, group in by_title.items():
        if len(group) == 1:
            out.append(group[0])
            continue

        title_lo = title.lower()
        is_recurring = bool(_RECURRING_RE.search(title_lo))
        is_promo = (
            any(phrase in title_lo for phrase in _PROMO_PHRASES)
            or bool(_DATE_IN_TITLE_RE.search(title))
        )

        if is_recurring and not is_promo:
            # Genuine weekly event — keep all occurrences.
            out.extend(group)
        else:
            # Billboard or ambiguous multi-date repeat — keep earliest only.
            group.sort(key=lambda e: e.get("date", ""))
            kept = group[0]
            # If the title names an explicit date (e.g. "June 6th"), use that
            # as the real event date instead of the first-billboarded date.
            corrected = _date_from_title(kept.get("title", ""), kept.get("date", ""))
            if corrected != kept.get("date"):
                kept = dict(kept)
                kept["date"] = corrected
            out.append(kept)

    return out


def scrape_kpcw_calendar():
    """Scrape KPCW's Tockify calendar. Returns (pc_events, heber_events)."""
    print("Scraping KPCW Community Calendar (Tockify API)...")
    pc_events, heber_events = [], []

    try:
        events = _fetch_all_tockify_events()
    except Exception as ex:
        print(f"  Error fetching Tockify API: {ex}")
        return [], []

    print(f"  Got {len(events)} raw events from Tockify")

    today_iso = datetime.now().strftime("%Y-%m-%d")
    seen_pc_keys = set()
    seen_heber_keys = set()
    dropped_past = 0
    dropped_dup = 0

    for raw in events:
        parsed = _parse_event(raw)
        if not parsed:
            continue
        if parsed["date"] < today_iso:
            dropped_past += 1
            continue

        # Route by location
        target_list = heber_events if _is_heber_location(parsed) else pc_events
        target_seen = seen_heber_keys if _is_heber_location(parsed) else seen_pc_keys

        key = (parsed["title"].lower().strip()[:40], parsed["date"][:10])
        if key in target_seen:
            dropped_dup += 1
            continue
        target_seen.add(key)
        target_list.append(parsed)

    pc_before = len(pc_events)
    pc_events = _collapse_billboards(pc_events)
    heber_events = _collapse_billboards(heber_events)
    if pc_before != len(pc_events):
        print(f"  Collapsed {pc_before - len(pc_events)} PC promotional billboards")
    print(f"  Sorted: {len(pc_events)} Park City + {len(heber_events)} Heber Valley")
    if dropped_past:
        print(f"  (Dropped {dropped_past} past-dated events)")
    if dropped_dup:
        print(f"  (Dropped {dropped_dup} internal duplicates)")

    return pc_events, heber_events


def _fetch_all_tockify_events():
    """Hit the Tockify API for the next 120 days. Paginate if needed."""
    all_events = []
    start_ms = int(datetime.now().timestamp() * 1000)
    end_ms = int((datetime.now() + timedelta(days=120)).timestamp() * 1000)

    # Tockify's `max` param caps at 200 per call. Use passback cursor to paginate.
    passback = None
    page = 0
    while True:
        page += 1
        params = {
            "calname": CALENDAR_NAME,
            "view": "agenda",
            "max": 200,
            "startms": start_ms,
            "endms": end_ms,
            "showAll": "false",
        }
        if passback:
            params["passback"] = passback

        r = requests.get(API_URL, params=params, timeout=20)
        if r.status_code != 200:
            raise Exception(f"API returned {r.status_code}")

        data = r.json()
        page_events = data.get("events", [])
        all_events.extend(page_events)

        meta = data.get("metaData") or {}
        passback = meta.get("passback")

        # Safety: stop after 10 pages or if no cursor returned
        if not passback or len(page_events) == 0 or page >= 10:
            break

    return all_events


def _parse_event(raw):
    """Convert one Tockify event into our standard schema."""
    try:
        content = raw.get("content") or {}
        when = raw.get("when") or {}
        start = when.get("start") or {}

        # Title — strip the auto-appended ", Month DD, YYYY" suffix Tockify adds
        title_raw = (content.get("summary") or {}).get("text") or ""
        title = _clean_title(title_raw)
        if not title or len(title) < 3:
            return None

        # Start datetime — millis is UTC-anchored epoch, but the time we want is
        # local-to-Park-City. Tockify gives us the timezone offset; apply it.
        start_ms = start.get("millis")
        offset_ms = start.get("offset", 0)
        if not start_ms:
            return None
        # Convert to local Park City time
        local_dt = datetime.fromtimestamp((start_ms + offset_ms) / 1000, tz=timezone.utc)
        date_iso = local_dt.strftime("%Y-%m-%d")

        all_day = when.get("allDay", False)
        start_time = None if all_day else local_dt.strftime("%-I:%M %p")

        # End time (optional)
        end_time = None
        end_block = when.get("end") or {}
        end_ms = end_block.get("millis")
        end_offset_ms = end_block.get("offset", offset_ms)
        if end_ms and not all_day:
            end_dt = datetime.fromtimestamp((end_ms + end_offset_ms) / 1000, tz=timezone.utc)
            end_time = end_dt.strftime("%-I:%M %p")
            # Multi-day events
            end_date_iso = end_dt.strftime("%Y-%m-%d")
        else:
            end_date_iso = None

        # Description (Tockify often truncates with ellipsis; keep up to 300 chars)
        description = (content.get("description") or {}).get("text") or ""
        description = re.sub(r"<[^>]+>", "", description).strip()[:2000]

        # Date sanity: Tockify often returns "billboard" events — the same
        # announcement repeated across many days leading up to the event, where
        # the API start timestamp is just the day the card appears, not the
        # real event date. The real date lives in the title or description
        # ("Park City Pride ... on Sunday, May 31, 2026"). Recover it.
        # Conservative: only override on a single clear future date, and only
        # forward (never move an event earlier).
        _today_iso = datetime.now().strftime("%Y-%m-%d")
        _corrected = _date_from_title(title, date_iso)
        if _corrected == date_iso:
            _corrected = _date_from_text(description, date_iso, _today_iso)
        if _corrected != date_iso and _corrected > date_iso:
            date_iso = _corrected
            # The API start_time belonged to the wrong (billboard) date; drop
            # it rather than show a misleading time on the real date.
            start_time = None
            end_date_iso = None
            end_time = None

        # Location: prefer the human-readable "place" + address
        place = content.get("place") or ""
        address = content.get("address") or ""
        if place and address:
            location = f"{place}, {address}"
        else:
            location = place or address or "Park City, UT"

        # Lat/lng
        loc_block = content.get("location") or {}
        lat = loc_block.get("latitude")
        lng = loc_block.get("longitude")

        # Categories
        tagset = (content.get("tagset") or {}).get("tags", {})
        tags = tagset.get("default", []) if isinstance(tagset, dict) else []

        # Detail link — prefer custom button (RSVP/tickets), fall back to calendar URL
        link = (content.get("customButtonLink") or "").strip()
        if not link:
            # Construct a deep link back to the event in the Tockify calendar
            eid = (raw.get("eid") or {}).get("uid") or ""
            if eid:
                link = f"https://tockify.com/{CALENDAR_NAME}/detail/{eid}/{start_ms}"
            else:
                link = SOURCE_URL

        event = {
            "title": title,
            "date": date_iso,
            "description": description,
            "location": location,
            "link": link,
            "source": SOURCE_NAME,
            "source_url": SOURCE_URL,
        }
        if start_time:
            event["start_time"] = start_time
        if end_time:
            event["end_time"] = end_time
        if end_date_iso and end_date_iso != date_iso:
            event["end_date"] = end_date_iso
        if lat is not None:
            event["lat"] = float(lat)
        if lng is not None:
            event["lng"] = float(lng)
        if tags:
            event["categories"] = tags

        return event

    except Exception as ex:
        # Defensive — never let one bad event kill the run
        # print(f"  (parse error on one event: {ex})")
        return None


def _clean_title(title):
    """Tockify auto-appends ', Month DD, YYYY' to every title. Strip it."""
    if not title:
        return ""
    # Match optional " - Month DD, YYYY" or ", Month DD, YYYY" at end of string
    pattern = r"[,\s\-–]+(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\s*$"
    return re.sub(pattern, "", title.strip()).strip()


def _is_heber_location(event):
    """Check if event location matches Heber Valley keywords."""
    blob = ((event.get("location") or "") + " " + (event.get("title") or "")).lower()
    return any(kw in blob for kw in HEBER_KEYWORDS)


if __name__ == "__main__":
    # Stand-alone test
    pc, heber = scrape_kpcw_calendar()
    print(f"\n=== Park City: {len(pc)} events ===")
    for e in pc[:5]:
        time_s = e.get("start_time", "(all day)")
        print(f"  {e['date']} {time_s} | {e['title'][:55]} | @ {e['location'][:50]}")
    print(f"\n=== Heber Valley: {len(heber)} events ===")
    for e in heber[:5]:
        time_s = e.get("start_time", "(all day)")
        print(f"  {e['date']} {time_s} | {e['title'][:55]} | @ {e['location'][:50]}")

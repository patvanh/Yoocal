#!/usr/bin/env python3
"""
Yoocal Scraper — Heber Valley / Wasatch Back Events
Sources:
  1. heberut.gov         — Heber City iCal feed (CivicEngage)
  2. midwaycityut.gov    — Midway City iCal feed
  3. SerpApi             — Google Events for Heber Valley, Midway, Kamas
  4. Hardcoded           — Known annual recurring events

Run: python3 heber_scraper.py
Output: events-heber.json
"""

import requests
import json
from event_classifier import classify_events
import re
import os
import urllib.request
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone

# Mountain Time for today_iso filtering
MOUNTAIN = timezone(timedelta(hours=-6))

SERPAPI_KEY = os.environ.get("SERPAPI_KEY", "")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

TODAY = datetime.now().strftime("%Y-%m-%d")


def normalize_date(s):
    if not s: return None
    s = str(s).strip()
    # ISO format: 2026-05-16
    m = re.match(r'(\d{4})-(\d{2})-(\d{2})', s)
    if m: return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"

    months = {'jan':'01','feb':'02','mar':'03','apr':'04','may':'05','jun':'06',
              'jul':'07','aug':'08','sep':'09','oct':'10','nov':'11','dec':'12',
              'january':'01','february':'02','march':'03','april':'04','june':'06',
              'july':'07','august':'08','september':'09','october':'10','november':'11','december':'12'}

    # "May 15, 2026" or "May 15 2026"
    m2 = re.search(r'(\w+)\s+(\d{1,2}),?\s+(\d{4})', s, re.I)
    if m2:
        mon = months.get(m2.group(1).lower())
        if mon: return f"{m2.group(3)}-{mon}-{m2.group(2).zfill(2)}"

    # "Thu, May 15" or "May 15" — assume current or next year
    m3 = re.search(r'(\w+)\s+(\d{1,2})(?:\s*[-–]\s*\w+\s+\d+)?$', s.strip(), re.I)
    if m3:
        mon = months.get(m3.group(1).lower())
        if mon:
            year = datetime.now().year
            day = int(m3.group(2))
            # If the date has passed this year, use next year
            candidate = f"{year}-{mon}-{str(day).zfill(2)}"
            if candidate < TODAY:
                candidate = f"{year+1}-{mon}-{str(day).zfill(2)}"
            return candidate

    # "15 May 2026"
    m4 = re.search(r'(\d{1,2})\s+(\w+)\s+(\d{4})', s, re.I)
    if m4:
        mon = months.get(m4.group(2).lower())
        if mon: return f"{m4.group(3)}-{mon}-{m4.group(1).zfill(2)}"

    return None

def extract_time(s):
    if not s: return ""
    m = re.search(r'\b(\d{1,2}:\d{2}\s?(?:AM|PM|am|pm))', str(s))
    return m.group(1).strip() if m else ""


# ─────────────────────────────────────────────
# 1. HEBER CITY iCAL — heberut.gov
# ─────────────────────────────────────────────
def scrape_google_events():
    print("Scraping Google Events via SerpApi...")
    events = []
    queries = [
        "events in Heber City Utah 2026",
        "events in Heber Valley Utah this weekend",
        "Midway Utah events 2026",
        "Kamas Utah events 2026",
        "Wasatch County Utah events 2026",
        "Heber Thursday Market on Main 2026",
        "things to do Heber Valley Utah summer 2026",
    ]
    seen = set()
    for query in queries:
        try:
            params = {
                "engine": "google_events",
                "q": query,
                "location": "Heber City, Utah, United States",
                "gl": "us", "hl": "en",
                "api_key": SERPAPI_KEY
            }
            r = requests.get("https://serpapi.com/search", params=params, timeout=15)
            if r.status_code != 200:
                print(f"  SerpApi {r.status_code} for '{query}'")
                continue
            results = r.json().get("events_results", [])
            all_keys = list(r.json().keys())
            print(f"  '{query}': {len(results)} results | response keys: {all_keys}")
            if not results and 'error' in r.json():
                print(f"    SerpApi error: {r.json()['error']}")
            if results:
                sample = results[0]
                print(f"    Sample: title='{sample.get('title')}' date={sample.get('date')}")

            for item in results:
                title = item.get("title", "").strip()
                if not title or len(title) < 3: continue

                date_info = item.get("date", {})
                when = date_info.get("when", "")
                start_date = date_info.get("start_date", "")
                date = normalize_date(start_date) or normalize_date(when)
                if not date or date < TODAY: continue

                key = f"{title.lower()[:40]}|{date}"
                if key in seen: continue
                seen.add(key)

                start_time = extract_time(when)
                address = item.get("address", [])
                location = ", ".join(address) if isinstance(address, list) else str(address) or "Heber Valley, UT"
                ticket_info = item.get("ticket_info", [])
                link = ticket_info[0].get("link", "") if ticket_info else item.get("link", "")
                description = item.get("description", "")
                is_free = "free" in description.lower() or "free" in title.lower()

                event = {
                    "title": title,
                    "date": date,
                    "description": description[:2000],
                    "location": location,
                    "link": link or f"https://www.google.com/search?q={title.replace(' ','+')}",
                    "source": "Google Events",
                    "source_url": "https://www.google.com",
                    "lat": 40.5069, "lng": -111.4133,
                    "scraped_at": datetime.now().isoformat()
                }
                if start_time: event["start_time"] = start_time
                if is_free: event["is_free"] = True
                events.append(event)
        except Exception as e:
            print(f"  Error for '{query}': {e}")
            continue

    print(f"  Found {len(events)} unique events from Google Events")
    return events


# ─────────────────────────────────────────────
# 4. HARDCODED — Known Annual Heber Valley Events
# ─────────────────────────────────────────────
def scrape_known_events():
    print("Loading known Heber Valley events...")
    events = []

    KNOWN = [
        # ── Heber Thursday Market on Main ──
        {
            "title": "Heber Thursday Market on Main",
            "date": "2026-06-04", "end_date": "2026-08-20",
            "start_time": "5:00 PM", "end_time": "9:00 PM",
            "recurrence": "weekly", "recurrence_day": "Thursday",
            "description": "Weekly outdoor market with food trucks, artisan booths, and free live concerts at 6:30pm. At Heber City Main Street Park.",
            "location": "Heber City Main Street Park, 250 S Main St, Heber City, UT 84032",
            "link": "https://hebermarket.com/heber-market-events/",
            "lat": 40.5069, "lng": -111.4133, "is_free": True,
        },
        # ── Soulful Sundays ──
        {
            "title": "Soulful Sundays Live Music",
            "date": "2026-06-07", "end_date": "2026-08-30",
            "start_time": "6:00 PM", "end_time": "7:00 PM",
            "recurrence": "weekly", "recurrence_day": "Sunday",
            "description": "Free Sunday evening live music at Heber City Main Street Park.",
            "location": "Heber City Main Street Park, 250 S Main St, Heber City, UT 84032",
            "link": "https://www.gohebervalley.com/events/",
            "lat": 40.5069, "lng": -111.4133, "is_free": True,
        },
        # ── Main Stage Live Music Mondays ──
        {
            "title": "Main Stage Live Music — Heber City",
            "date": "2026-06-01", "end_date": "2026-08-31",
            "start_time": "6:30 PM", "end_time": "8:00 PM",
            "recurrence": "weekly", "recurrence_day": "Monday",
            "description": "Free Monday evening live music at Heber City Main Street Park.",
            "location": "Heber City Main Street Park, 250 S Main St, Heber City, UT 84032",
            "link": "https://www.gohebervalley.com/events/",
            "lat": 40.5069, "lng": -111.4133, "is_free": True,
        },
        # ── Midway Music on the Square ──
        {
            "title": "Midway Music on the Square",
            "date": "2026-06-03", "end_date": "2026-08-26",
            "start_time": "6:00 PM",
            "recurrence": "weekly", "recurrence_day": "Wednesday",
            "description": "Free Wednesday evening live music at Midway Town Square.",
            "location": "Midway Town Square, 75 N 100 W, Midway, UT 84049",
            "link": "https://www.gohebervalley.com/events/",
            "lat": 40.5127, "lng": -111.4742, "is_free": True,
        },
        # ── Midway Swiss Days ──
        {
            "title": "Midway Swiss Days",
            "date": "2026-09-04", "end_date": "2026-09-05",
            "start_time": "8:00 AM", "end_time": "8:00 PM",
            "description": "Utah's second largest festival. Free 10K run at 7am, parade at 10am, live entertainment, food vendors, artisan booths. Free admission.",
            "location": "151 W Main Street, Midway, UT 84049",
            "link": "https://www.gohebervalley.com/swiss-days/",
            "lat": 40.5127, "lng": -111.4742, "is_free": True, "featured": True,
        },
        # ── Wasatch County Fair ──
        {
            "title": "Wasatch County Fair",
            "date": "2026-07-28", "end_date": "2026-08-01",
            "start_time": "10:00 AM",
            "description": "Annual county fair with rides, livestock, rodeo, live entertainment, food, and one of the biggest demolition derbies in the western US.",
            "location": "Wasatch County Fairgrounds, Heber City, UT 84032",
            "link": "https://www.gohebervalley.com/events/",
            "lat": 40.5069, "lng": -111.4133, "featured": True,
        },
        # ── Heber City 4th of July ──
        {
            "title": "Heber City 4th of July Celebration",
            "date": "2026-07-04",
            "start_time": "9:00 AM",
            "description": "Annual 4th of July parade, fireworks, and celebration in Heber City.",
            "location": "Heber City, UT 84032",
            "link": "https://www.heberut.gov/Calendar.aspx",
            "lat": 40.5069, "lng": -111.4133,
        },
        # ── Heber Valley Railroad ──
        {
            "title": "Heber Valley Railroad Excursion",
            "date": "2026-05-16", "end_date": "2026-10-31",
            "start_time": "11:00 AM",
            "recurrence": "weekly", "recurrence_days": "Saturday,Sunday",
            "description": "Scenic train rides through Heber Valley on a historic railroad. Multiple excursions available including dinner trains and special events.",
            "location": "Heber Valley Railroad, 450 S 600 W, Heber City, UT 84032",
            "link": "https://hebervalleyrailroad.org",
            "lat": 40.5040, "lng": -111.4080,
        },
        # ── Deer Creek State Park ──
        {
            "title": "Deer Creek State Park — Open Season",
            "date": "2026-05-01", "end_date": "2026-09-30",
            "description": "Boating, fishing, swimming, and camping at Deer Creek Reservoir. 20 minutes from Park City via Hwy 189.",
            "location": "Deer Creek State Park, 4000 UT-189, Midway, UT 84049",
            "link": "https://stateparks.utah.gov/parks/deer-creek/",
            "lat": 40.4100, "lng": -111.5300,
        },
        # ── Kamas Valley Cattle Drive ──
        {
            "title": "Kamas Valley Cattle Drive",
            "date": "2026-06-06",
            "start_time": "8:00 AM",
            "description": "Annual cattle drive through Kamas Valley — a Utah tradition. Free to watch.",
            "location": "Kamas, UT 84036",
            "link": "https://www.gohebervalley.com/events/",
            "lat": 40.6430, "lng": -111.2797, "is_free": True,
        },
    ]

    for e in KNOWN:
        if e.get("end_date", e["date"]) >= TODAY:
            event = {
                "title": e["title"],
                "date": e["date"],
                "description": e.get("description", ""),
                "location": e.get("location", "Heber Valley, UT"),
                "link": e.get("link", "https://www.gohebervalley.com/events/"),
                "source": "Heber Valley Tourism",
                "source_url": "https://www.gohebervalley.com/events/",
                "lat": e.get("lat", 40.5069),
                "lng": e.get("lng", -111.4133),
                "scraped_at": datetime.now().isoformat()
            }
            for field in ["start_time", "end_time", "end_date", "recurrence",
                          "recurrence_day", "recurrence_days", "is_free", "featured"]:
                if e.get(field): event[field] = e[field]
            events.append(event)

    print(f"  Loaded {len(events)} known Heber Valley events")
    return events


# ─────────────────────────────────────────────
# DEDUP & SAVE
# ─────────────────────────────────────────────
# ─────────────────────────────────────────────
# 5. EVENTBRITE — via SerpApi (JS-rendered site)
# ─────────────────────────────────────────────
def scrape_eventbrite():
    print("Scraping Eventbrite for Heber Valley events...")
    events = []
    try:
        params = {
            "engine": "google_events",
            "q": "eventbrite Heber Valley Utah events 2026",
            "location": "Heber City, Utah, United States",
            "api_key": SERPAPI_KEY
        }
        r = requests.get("https://serpapi.com/search", params=params, timeout=15)
        results = r.json().get("events_results", [])
        print(f"  Eventbrite SerpApi: {len(results)} results")
        for item in results:
            title = item.get("title","").strip()
            if not title: continue
            date_info = item.get("date", {})
            when = date_info.get("when","")
            date = normalize_date(date_info.get("start_date","")) or normalize_date(when)
            if not date or date < TODAY: continue
            key = f"{title.lower()[:40]}|{date}"
            start_time = extract_time(when)
            address = item.get("address",[])
            location = ", ".join(address) if isinstance(address, list) else str(address) or "Heber Valley, UT"
            ticket_info = item.get("ticket_info",[])
            link = ticket_info[0].get("link","") if ticket_info else item.get("link","")
            event = {
                "title": title, "date": date,
                "description": item.get("description","")[:2000],
                "location": location,
                "link": link or "https://www.eventbrite.com/d/ut--heber/events/",
                "source": "Eventbrite",
                "source_url": "https://www.eventbrite.com/d/ut--heber/events/",
                "lat": 40.5069, "lng": -111.4133,
                "scraped_at": datetime.now().isoformat()
            }
            if start_time: event["start_time"] = start_time
            events.append(event)
    except Exception as e:
        print(f"  Eventbrite error: {e}")
    print(f"  Found {len(events)} events from Eventbrite")
    return events


# ─────────────────────────────────────────────
# 6. RUNNING IN THE USA — Heber Valley races
# ─────────────────────────────────────────────


def scrape_slrc_heber_wrapper():
    """Heber events from Salt Lake Running Co via Elfsight API."""
    try:
        from slrc_scraper import scrape_slrc_heber
    except ImportError:
        return []
    try:
        return scrape_slrc_heber()
    except Exception as ex:
        print(f"  SLRC Heber scraper failed: {ex}")
        return []


def scrape_dainty_pear_wrapper():
    """Midway boutique class calendar via Shopify products JSON.

    Source: thedaintypearco.com/collections/classes. Returns ~3-15 classes/year
    (cookie decorating, oil painting, mahjong, etc.) at 152 W 100 N Midway.
    """
    try:
        from dainty_pear_scraper import scrape_dainty_pear
    except ImportError:
        return []
    try:
        return scrape_dainty_pear()
    except Exception as ex:
        print(f"  Dainty Pear scraper failed: {ex}")
        return []


def scrape_runsignup():
    """Heber Valley races via RunSignup public API.

    Replaces the old hardcoded race list + runningintheusa.com HTML scrape
    (the HTML scrape was 403'd by Cloudflare anyway). Now uses RunSignup's
    REST API, which auto-discovers all races in Heber City / Midway / Kamas.
    """
    try:
        from runsignup_scraper import scrape_runsignup_heber
    except ImportError:
        print("  runsignup_scraper not available, skipping")
        return []
    try:
        return scrape_runsignup_heber()
    except Exception as ex:
        print(f"  RunSignup Heber scraper failed: {ex}")
        return []

def deduplicate(events):
    seen = set()
    unique = []
    for e in events:
        title = re.sub(r'\s+', ' ', e["title"].lower().strip())
        title_clean = re.sub(r'^[\(\"\'\-\s]+', '', title)[:35]
        date = e.get("date", "")[:10]
        key = f"{title_clean}|{date}"
        if key not in seen:
            seen.add(key)
            unique.append(e)
    return unique

def save_events(events, filename="public/raw/events-heber.json"):
    # Apply canonical category classification before writing.
    from event_classifier import classify_events as _classify_events
    events = _classify_events(events)

    output = {
        "updated_at": datetime.now().isoformat(),
        "total": len(events),
        "events": events
    }
    with open(filename, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nSaved {len(events)} events to {filename}")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
EVENTS_URL = "https://www.gohebervalley.com/events/"
CARD_SELECTOR = "a.pinnable_item"

MONTH_MAP = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}


def scrape_gohebervalley_live():
    """Scrape gohebervalley.com/events/ via universal_scraper.
    Replaces old Playwright function whose CSS selector broke."""
    try:
        from universal_scraper import scrape_gohebervalley
        return scrape_gohebervalley()
    except Exception as e:
        print(f"  [scrape_gohebervalley_live] failed: {e}")
        return []

def parse_card(card_element):
    """Parse one <a class='pinnable_item'> into an event dict.

    Returns None if the card looks like navigation (no real event title)
    or if the text doesn't match the expected 4-5 line pattern.
    """
    text = (card_element.inner_text() or "").strip()
    if not text:
        return None

    href = card_element.get_attribute("href") or ""
    if href and not href.startswith("http"):
        href = "https://www.gohebervalley.com" + href

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if len(lines) < 4:
        # Could be the "Chamber Events" nav link with just 2-3 lines —
        # not a real event
        return None

    month_text = lines[0]
    day_text = lines[1]
    # lines[2] is category, used to enrich description
    category = lines[2] if len(lines) > 2 else ""
    title = lines[3] if len(lines) > 3 else ""
    time_date_line = lines[4] if len(lines) > 4 else ""

    # Sanity check: month should be a 3-letter all-caps abbreviation
    if not re.match(r"^[A-Z]{3,9}$", month_text):
        return None

    month_num = MONTH_MAP.get(month_text.lower())
    if not month_num:
        return None

    # Parse the day. "15+" means multi-day starting on the 15th.
    m = re.match(r"^(\d{1,2})(\+)?$", day_text)
    if not m:
        return None
    day = int(m.group(1))
    is_multi_day = bool(m.group(2))

    # Build the start date. Year isn't shown — assume current year, but if
    # the resulting date is more than a month in the past, roll forward.
    today = datetime.now().date()
    try:
        start_date = datetime(today.year, month_num, day).date()
    except ValueError:
        return None
    if (today - start_date).days > 30:
        try:
            start_date = datetime(today.year + 1, month_num, day).date()
        except ValueError:
            return None

    end_date = None
    start_time, end_time = None, None

    if time_date_line:
        # Try several patterns in order. First, embedded date range like
        # "Fri, May 8 - Jun 12, 9:00 - 10:00 AM" — we want both date range
        # and time range.
        ed = extract_explicit_end_date(time_date_line, start_date.year, month_num)
        if ed:
            end_date = ed

        # "May 15 - 16, 10:00 AM - 6:00 PM" — same month, different day
        m = re.search(
            r"\b([A-Za-z]+)\s+(\d{1,2})\s*[-–]\s*(\d{1,2})\b",
            time_date_line,
        )
        if m and not end_date:
            em = MONTH_MAP.get(m.group(1).lower())
            if em == month_num:
                try:
                    end_date = datetime(start_date.year, em, int(m.group(3))).date()
                except ValueError:
                    pass

        # Time range
        start_time, end_time = parse_time_range(time_date_line)

    return {
        "title": title,
        "date": start_date.isoformat(),
        "end_date": end_date.isoformat() if end_date else None,
        "start_time": start_time,
        "end_time": end_time,
        "location": extract_venue_from_title(title) or "Heber Valley, UT",
        "description": category,
        "link": href,
        "lat": None,
        "lng": None,
    }


def extract_explicit_end_date(text, year_hint, start_month):
    """For multi-day spans like 'May 8 - Jun 12' or 'Fri, May 8 - Jun 12'."""
    m = re.search(
        r"\b([A-Za-z]+)\s+(\d{1,2})\s*[-–]\s*([A-Za-z]+)\s+(\d{1,2})\b",
        text,
    )
    if m:
        em = MONTH_MAP.get(m.group(3).lower())
        if em:
            try:
                return datetime(year_hint, em, int(m.group(4))).date()
            except ValueError:
                pass
    return None


def parse_time_range(text):
    """Extract '10:00 AM' / '6:00 PM' style start and end times."""
    # Case A: explicit "10:00 AM - 6:00 PM" (AM/PM on both)
    m = re.search(
        r"(\d{1,2}:\d{2}\s*[AaPp][Mm])\s*[-–]\s*(\d{1,2}:\d{2}\s*[AaPp][Mm])",
        text,
    )
    if m:
        return normalize_time(m.group(1)), normalize_time(m.group(2))

    # Case B: "10:30 - 11:30 AM" (AM/PM only on the end — share it with start)
    m = re.search(
        r"(\d{1,2}:\d{2})\s*[-–]\s*(\d{1,2}:\d{2})\s*([AaPp][Mm])",
        text,
    )
    if m:
        ampm = m.group(3).upper()
        return normalize_time(f"{m.group(1)} {ampm}"), normalize_time(f"{m.group(2)} {ampm}")

    # Case C: single time
    m = re.search(r"(\d{1,2}:\d{2}\s*[AaPp][Mm])", text)
    if m:
        return normalize_time(m.group(1)), None

    return None, None


def normalize_time(t):
    """Normalize '9:00 am' -> '9:00 AM'."""
    return re.sub(r"\s+", " ", t.strip()).upper()


def extract_venue_from_title(title):
    """Many titles encode the venue inline: 'Event Name @ Venue Name'."""
    if not title or "@" not in title:
        return None
    parts = title.split("@", 1)
    if len(parts) == 2:
        venue = parts[1].strip()
        if venue:
            return venue + ", Heber Valley, UT"
    return None


def scrape_hebervalleylife_sitemap():
    """Scrape hebervalleylife.com via its MEC events sub-sitemap.

    Discovered via discover_sources_v3.py — local Heber Valley life/events site
    running WordPress Modern Events Calendar plugin. Each event detail page has
    clean Schema.org Event JSON-LD.
    """
    try:
        from sitemap_event_scraper import scrape_sitemap_events
    except ImportError:
        print("[hebervalleylife] sitemap_event_scraper not available")
        return []
    try:
        return scrape_sitemap_events(
            sitemap_url="https://hebervalleylife.com/wp-sitemap-posts-mec-events-1.xml",
            url_pattern=r"/events/",
            source_name="Heber Valley Life",
            default_lat=40.5066,
            default_lng=-111.4133,
            default_city="Heber City, UT",
            default_categories=["Community"],
            # This MEC sitemap lists 1100+ events going back to 2021. Current
            # events get re-edited (lastmod bumped) each season, so an 8-month
            # window prunes the dead historical pages while keeping everything
            # plausibly upcoming. Cuts ~1100 fetches to ~100; per-page crawl
            # still does the real future-date filtering.
            min_lastmod_days=240,
        )
    except Exception as ex:
        print(f"[hebervalleylife] failed: {ex}")
        return []


# City coordinates for TownLift events. TownLift covers BOTH Park City and
# Heber Valley, so we can't pick one default — instead we detect per event.
_PC_COORDS = (40.6461, -111.4980)
_HB_COORDS = (40.5069, -111.4133)

# Lowercase keyword sets. Order matters in conflict resolution (PC wins ties
# because TownLift is a Park City publication and ambiguous events lean PC).
_PC_SIGNALS = [
    "park city", "deer valley", "kimball", "egyptian", "pcmr", "main street pc",
    "canyons village", "snyderville", "prospector", "newpark", "sundance",
]
_HB_SIGNALS = [
    "heber", "midway", "soldier hollow", "wasatch back", "kamas",
    "jordanelle", "deer creek reservoir", "francis", "oakley",
    "homestead", "wasatch county",
]

def _detect_townlift_city(title: str, description: str, venue_text: str = ""):
    """Return ('parkcity', lat, lng, label) | ('heber', lat, lng, label) | None.

    `label` is the human-readable city string for the location field.
    """
    haystack = " ".join([title or "", description or "", venue_text or ""]).lower()
    pc_hit = any(s in haystack for s in _PC_SIGNALS)
    hb_hit = any(s in haystack for s in _HB_SIGNALS)
    if pc_hit and not hb_hit:
        return ("parkcity", _PC_COORDS[0], _PC_COORDS[1], "Park City, UT")
    if hb_hit and not pc_hit:
        return ("heber", _HB_COORDS[0], _HB_COORDS[1], "Heber City, UT")
    if pc_hit and hb_hit:
        # Both signals present (e.g. an event "in Park City" mentions Heber
        # in passing). PC wins on conflict — TownLift is PC-based and ambiguous
        # events more often skew PC than the reverse.
        return ("parkcity", _PC_COORDS[0], _PC_COORDS[1], "Park City, UT")
    return None


def scrape_townlift():
    """Scrape townlift.com (Wasatch Back news outlet) via WordPress Tribe API.

    Discovered via discover_sources_v3.py. Regional paper — covers Heber,
    Midway, Kamas, Park City. TownLift's API doesn't always include venue
    data, so per-event city detection from the title/description text is the
    only honest signal we have.
    """
    try:
        from wp_tribe_events_scraper import scrape_wp_tribe_events
    except ImportError:
        print("[townlift] wp_tribe_events_scraper not available")
        return []
    try:
        # Pass NO default city/coords — TownLift covers both cities. We assign
        # them per event below based on text signals.
        events = scrape_wp_tribe_events(
            base_url="https://www.townlift.com",
            source_name="TownLift",
            default_lat=None,
            default_lng=None,
            default_city=None,
            default_categories=["Community"],
        )
    except Exception as ex:
        print(f"[townlift] failed: {ex}")
        return []

    # LLM-based per-event address extraction: fetch each event page, extract
    # venue + street + city + zip with Claude, geocode via Nominatim. Cached
    # per URL so re-scrapes only do new events.
    try:
        from townlift_address_enricher import enrich_townlift_events
        events = enrich_townlift_events(events)
    except ImportError:
        print("  [townlift] enricher not available, skipping LLM extraction")
    except Exception as ex:
        print(f"  [townlift] enricher error (continuing with keyword fallback): {ex}")

    # Keyword/zip fallback for any events the enricher couldn't resolve.
    pc_count = hb_count = unknown = 0
    for e in events:
        # If wp_tribe already parsed a real venue, trust it — don't override.
        # Heuristic: venue is "real" if location isn't None/empty/"Location TBD".
        loc = (e.get("location") or "").strip()
        has_real_venue = loc and loc != "Location TBD"

        if has_real_venue:
            # Still infer coords from text if missing (radius filter needs them).
            if e.get("lat") is None or e.get("lng") is None:
                detected = _detect_townlift_city(e.get("title", ""), e.get("description", ""), loc)
                if detected:
                    _, lat, lng, _ = detected
                    e["lat"] = lat
                    e["lng"] = lng
            continue

        # No real venue → detect city from text.
        detected = _detect_townlift_city(e.get("title", ""), e.get("description", ""))
        if detected is None:
            unknown += 1
            # Leave location empty; event will lack coords too. Master build will
            # keep it (no-coord events pass radius filter), so it may appear in
            # multiple cities — acceptable for the few unknowns.
            continue
        city_key, lat, lng, label = detected
        e["lat"] = lat
        e["lng"] = lng
        e["location"] = label
        if city_key == "parkcity":
            pc_count += 1
        else:
            hb_count += 1

    print(f"  [townlift] city detection: {pc_count} Park City, {hb_count} Heber, {unknown} unknown")
    return events


def scrape_running_in_the_usa_heber():
    """Heber Valley races from runningintheusa.com via Firecrawl.

    The site hard-blocks direct HTTP (403), so we fetch via Firecrawl + Claude
    extraction (same working pattern as Park City / Jackson). Uses the
    Heber-direct list URL (NOT within-25-miles, which sweeps in Provo/SLC/Park
    City races). Complements RunSignup, which only surfaces a few Heber races.
    """
    print("Scraping runningintheusa.com for Heber races (via Firecrawl)...")
    try:
        from firecrawl_extractor import extract_events_from_url
        evs = extract_events_from_url(
            url="https://www.runningintheusa.com/race/list/heber%20city-ut/upcoming",
            source_name="RunningInTheUSA Heber",
            default_lat=40.5069, default_lng=-111.4133,
            default_city="Heber City, UT",
            default_categories=["Running & Races"],
        )
        print(f"  RunningInTheUSA Heber returned {len(evs)} races")
        return evs
    except Exception as ex:
        print(f"  RunningInTheUSA Heber scrape failed: {ex}")
        return []


def scrape_wasatch_parks_rec():
    """Wasatch County Parks & Rec / Event Complex (Heber).

    The event LISTING is JS-rendered (Saffire postbacks) and can't be scraped
    directly -- but the sitemap lists every event detail page, and those ARE
    server-rendered. So: read the sitemap, keep /events/<year>/<slug> URLs,
    fetch each detail page, and parse title/date/image from the static HTML.
    Low volume but unique to Heber (Fair Days, the Miss Wasatch pageant, the
    rodeos, the demolition derby).
    """
    print("Scraping Wasatch County Parks & Rec (sitemap + detail pages)...")
    BASE = "https://www.wasatchparksandrec.com"
    HEADERS = {"User-Agent": "Mozilla/5.0 (yoocal events aggregator)"}
    MONTHS = {m[:3].lower(): i for i, m in enumerate(
        ["January", "February", "March", "April", "May", "June", "July",
         "August", "September", "October", "November", "December"], 1)}
    today = datetime.now().date()

    def _iso(mon, day, yr):
        mi = MONTHS.get(str(mon)[:3].lower())
        return f"{yr:04d}-{mi:02d}-{int(day):02d}" if mi else None

    def _parse_dates(text):
        text = text.replace("\xa0", " ")
        ym = re.search(r"(20\d{2})", text)
        if not ym:
            return None, None
        year = int(ym.group(1))
        pairs = re.findall(r"([A-Za-z]{3,9})\.?\s+(\d{1,2})\b", text)
        if not pairs:
            return None, None
        start = _iso(pairs[0][0], pairs[0][1], year)
        end = start
        if len(pairs) >= 2:
            end = _iso(pairs[1][0], pairs[1][1], year) or start
        else:
            rng = re.search(r"\d{1,2}\s*[-\u2013]\s*(\d{1,2})", text)
            if rng:
                end = _iso(pairs[0][0], rng.group(1), year) or start
        if start and end and end < start:  # range crosses New Year
            end = f"{year + 1}{end[4:]}"
        return start, end

    def _norm_time(t):
        m = re.match(r"(\d{1,2}:\d{2})\s*([AaPp][Mm])", t)
        return f"{m.group(1)} {m.group(2).upper()}" if m else ""

    def _meta(html, prop):
        m = re.search(r'<meta[^>]+(?:property|name)=["\']' + re.escape(prop)
                      + r'["\'][^>]*content=["\']([^"\']*)["\']', html, re.I)
        return m.group(1).strip() if m else ""

    try:
        sm = requests.get(f"{BASE}/sitemap.xml", headers=HEADERS, timeout=20).text
    except Exception as ex:
        print(f"  Wasatch sitemap fetch failed: {ex}")
        return []

    urls = list(dict.fromkeys(
        re.findall(r"<loc>([^<]*/events/\d{4}/[^<]+)</loc>", sm)))
    print(f"  Found {len(urls)} event detail URLs in sitemap")

    out = []
    for u in urls:
        try:
            html = requests.get(u, headers=HEADERS, timeout=20).text
        except Exception:
            continue
        title = _meta(html, "og:title")
        if not title or len(title) < 3:
            continue
        tl = title.lower()
        if any(p in tl for p in ("registration", "information", "camping")):
            continue  # admin/registration/info pages, not real attendee events
        text = re.sub(r"<[^>]+>", " ", html)
        dm = re.search(r"Date:\s*([A-Za-z0-9 ,\u2013\-]+?20\d{2})", text)
        start, end = _parse_dates(dm.group(1)) if dm else (None, None)
        if not start or start < today.isoformat():
            continue  # undated (sign-up/release pages) or already past
        tm = re.search(r"(\d{1,2}:\d{2}\s*[AaPp][Mm])", text)
        out.append({
            "title": title,
            "date": start,
            "end_date": end or start,
            "start_time": _norm_time(tm.group(1)) if tm else "",
            "location": "Heber City, UT",
            "venue_name": "Wasatch County Event Complex",
            "description": _meta(html, "og:description"),
            "link": u,
            "source": "Wasatch County Parks & Rec",
            "source_url": f"{BASE}/events",
            "image_url": _meta(html, "og:image"),
            "lat": 40.4897, "lng": -111.4133,
            "city": "Heber City, UT",
            "categories": ["Community"],
        })
    print(f"  Wasatch County Parks & Rec returned {len(out)} events")
    return out


def main():
    print("=" * 55)
    print("  Yoocal Heber Valley Scraper")
    print("=" * 55)
    print()

    all_events = []
    # Pick up any Heber events KPCW scraper cached for us (KPCW covers both
    # Park City and Heber, so we run it once from scraper.py and share results).
    kpcw_cache_path = "kpcw_heber_cache.json"
    if os.path.exists(kpcw_cache_path):
        try:
            with open(kpcw_cache_path) as f:
                kpcw_data = json.load(f)
            kpcw_events = kpcw_data.get("events", [])
            if kpcw_events:
                all_events += kpcw_events
                print(f"Loaded {len(kpcw_events)} Heber events from KPCW cache")
        except Exception as ex:
            print(f"Warning: could not load {kpcw_cache_path}: {ex}")

    browser_scraped = scrape_gohebervalley_live()
    hv_events = browser_scraped if browser_scraped else scrape_known_events()

    # Enrich Heber Valley Tourism events with full date ranges + recurrence by
    # visiting each detail page (the listings only show start dates).
    try:
        from heber_valley_enricher import enrich_heber_valley_events
        hv_events = enrich_heber_valley_events(hv_events)
    except ImportError:
        print("  [hv-enrich] enricher not available, skipping detail-page enrichment")
    except Exception as ex:
        print(f"  [hv-enrich] enricher error (continuing without enrichment): {ex}")

    all_events += hv_events
    all_events += scrape_google_events()
    all_events += scrape_eventbrite()
    all_events += scrape_runsignup()
    all_events += scrape_running_in_the_usa_heber()
    all_events += scrape_wasatch_parks_rec()
    all_events += scrape_slrc_heber_wrapper()
    all_events += scrape_dainty_pear_wrapper()
    all_events += scrape_hebervalleylife_sitemap()
    all_events += scrape_townlift()

    print(f"\nTotal raw events: {len(all_events)}")
    unique = deduplicate(all_events)
    print(f"After deduplication: {len(unique)}")

    save_events(unique)

    print("\nDone! Sample events:")
    for e in unique[:10]:
        print(f"  [{e['source']}] {e['title']} -- {e['date']} {e.get('start_time', '')}")

if __name__ == "__main__":
    main()

# ─────────────────────────────────────────────
# 5. EVENTBRITE — Heber Valley events
# ─────────────────────────────────────────────
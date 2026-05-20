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
                    "description": description[:300],
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
                "description": item.get("description","")[:300],
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

def save_events(events, filename="public/events-heber.json"):
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
    """Scrape gohebervalley.com/events/ using Playwright. Never raises."""
    print("Scraping gohebervalley.com (Playwright)...")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  Playwright not installed; skipping. Run: pip install playwright && playwright install chromium")
        return []

    events = []

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 1800},
            )
            page = context.new_page()

            print(f"  Loading {EVENTS_URL} ...")
            page.goto(EVENTS_URL, wait_until="networkidle", timeout=60000)

            # Wait until at least one event card has rendered, then give it
            # a beat to render the rest.
            try:
                page.wait_for_selector(CARD_SELECTOR, timeout=15000)
            except Exception:
                print("  Warning: no event cards appeared within 15s")
                browser.close()
                return []

            page.wait_for_timeout(2000)  # let the async batch complete

            cards = page.query_selector_all(CARD_SELECTOR)
            print(f"  Found {len(cards)} candidate cards")

            seen_keys = set()
            for card in cards:
                try:
                    ev = parse_card(card)
                    if not ev:
                        continue
                    # Dedupe by (title, date)
                    key = (ev["title"], ev["date"])
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)
                    events.append(ev)
                except Exception:
                    continue

            browser.close()

    except Exception as ex:
        print(f"  Playwright failed: {ex}")
        return []

    # Decorate with source metadata
    for e in events:
        e.setdefault("source", "Heber Valley Tourism")
        e.setdefault("source_url", "https://www.gohebervalley.com/events/")

    print(f"  Extracted {len(events)} events from gohebervalley.com")
    return events


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
        )
    except Exception as ex:
        print(f"[hebervalleylife] failed: {ex}")
        return []


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
    if browser_scraped:
        all_events += browser_scraped
    else:
        all_events += scrape_known_events()
    all_events += scrape_google_events()
    all_events += scrape_eventbrite()
    all_events += scrape_runsignup()
    all_events += scrape_slrc_heber_wrapper()
    all_events += scrape_hebervalleylife_sitemap()

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
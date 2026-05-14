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
import re
import os
import urllib.request
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

SERPAPI_KEY = "f0e24bf0ff2e97c60a99322c2efd147645362de5b54c8f2d913ed4af2bc4a5bd"

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
def scrape_runsignup():
    print("Scraping runningintheusa.com for Heber Valley races...")
    events = []
    TODAY = datetime.now().strftime("%Y-%m-%d")

    # Hardcoded known Heber Valley races from runningintheusa.com
    KNOWN_RACES = [
        {"title": "Heber Valley Main-to-Main 5K and 10K", "date": "2026-07-04", "start_time": "7:30 AM",
         "location": "Heber City, UT 84032", "link": "https://runsignup.com/Race/UT/HeberCity/HeberValleyMaintoMain"},
        {"title": "Runtastic HEBER Half Marathon", "date": "2026-08-08", "start_time": "6:00 AM",
         "location": "1600 E 980th S, Heber City, UT 84032",
         "link": "https://runsignup.com/Race/UT/Heber/HeberHalfand5K",
         "description": "Run for Autism. All-downhill half marathon through Heber Valley with stunning mountain views of the Wasatch."},
        {"title": "High Uinta Half Marathon", "date": "2026-07-25", "start_time": "7:00 AM",
         "location": "Kamas, UT 84036", "link": "https://runsignup.com/Race/UT/Kamas/HighUintaHalfMarathon"},
        {"title": "Swiss Days 10K Run", "date": "2026-09-05", "start_time": "7:00 AM",
         "location": "151 W Main Street, Midway, UT 84049",
         "link": "https://www.gohebervalley.com/swiss-days/",
         "description": "Annual Swiss Days 10K run in Midway, part of the Swiss Days festival on Labor Day weekend."},
        {"title": "Wasatch Peak 5K", "date": "2026-05-02", "start_time": "8:00 AM",
         "location": "Heber City, UT 84032", "link": "https://runsignup.com/Race/UT/HeberCity/WasatchPeak5K"},
    ]
    for race in KNOWN_RACES:
        if race["date"] >= TODAY:
            event = {
                "title": race["title"], "date": race["date"],
                "description": race.get("description", f"Running race in {race['location']}."),
                "location": race["location"], "link": race["link"],
                "source": "Running in the USA",
                "source_url": "https://www.runningintheusa.com",
                "lat": 40.5069, "lng": -111.4133,
                "scraped_at": datetime.now().isoformat()
            }
            if race.get("start_time"): event["start_time"] = race["start_time"]
            events.append(event)

    # Dynamic scrape with correct URL format (city name with %20 not hyphen)
    for city_url, city_name in [("heber%20city-ut","Heber City"), ("midway-ut","Midway"), ("kamas-ut","Kamas")]:
        try:
            url = f"https://www.runningintheusa.com/race/list/{city_url}/upcoming"
            r = requests.get(url, headers=HEADERS, timeout=15)
            soup = BeautifulSoup(r.text, "html.parser")
            for row in soup.find_all("tr"):
                cells = row.find_all("td")
                if len(cells) < 2: continue
                tel = cells[0].find("a") or cells[0]
                title = tel.get_text(strip=True)
                if not title or len(title) < 3: continue
                link = tel.get("href","") if getattr(tel,"name",None)=="a" else ""
                if link and not link.startswith("http"): link = "https://www.runningintheusa.com" + link
                date = normalize_date(cells[1].get_text(strip=True))
                if not date or date < TODAY: continue
                loc = cells[2].get_text(strip=True) if len(cells) > 2 else f"{city_name}, UT"
                events.append({"title": title, "date": date,
                    "description": f"Running race in {loc}.",
                    "location": loc, "link": link or url,
                    "source": "Running in the USA", "source_url": url,
                    "lat": 40.5069, "lng": -111.4133,
                    "scraped_at": datetime.now().isoformat()
                })
        except Exception as e:
            print(f"  runningintheusa {city_name}: {e}")

    print(f"  Found {len(events)} events from running sites")
    return events

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

def save_events(events, filename="events-heber.json"):
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
def scrape_gohebervalley_live():
    """Load events from browser-scraped gohebervalley-live.json if it exists."""
    import os
    paths = [
        os.path.expanduser("~/Downloads/gohebervalley-live.json"),
        os.path.join(os.path.dirname(__file__), "gohebervalley-live.json"),
    ]
    for path in paths:
        if os.path.exists(path):
            print(f"Loading gohebervalley.com events from {path}...")
            try:
                with open(path) as f:
                    data = json.load(f)
                events = data.get("events", [])
                for e in events:
                    e["source"] = "Heber Valley Tourism"
                    e["source_url"] = "https://www.gohebervalley.com/events/"
                print(f"  Loaded {len(events)} events from gohebervalley.com")
                return events
            except Exception as ex:
                print(f"  Error loading {path}: {ex}")
    print("  No gohebervalley-live.json found, skipping")
    return []


def main():
    print("=" * 55)
    print("  Yoocal Heber Valley Scraper")
    print("=" * 55)
    print()

    all_events = []
    browser_scraped = scrape_gohebervalley_live()
    if browser_scraped:
        all_events += browser_scraped
    else:
        all_events += scrape_known_events()
    all_events += scrape_google_events()
    all_events += scrape_eventbrite()
    all_events += scrape_runsignup()

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
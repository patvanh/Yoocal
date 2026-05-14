#!/usr/bin/env python3
"""
Yoocal Scraper — Elkhart Lake, WI Events
Sources:
  1. elkhartlake.com       — official tourism events
  2. Road America          — hardcoded full 2026 season + scraped calendar
  3. siebkens.com          — live music events
  4. visitsheboygancounty.com — county tourism events
  5. patch.com             — community events
  6. elkhartlakewi.gov     — village calendar
  7. SerpApi Google Events — Google Events for Elkhart Lake

Run: python3 elkhart_scraper.py
Output: events-elkhartlake.json
"""

import requests
import json
import re
import os
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

SERPAPI_KEY = "f0e24bf0ff2e97c60a99322c2efd147645362de5b54c8f2d913ed4af2bc4a5bd"

def normalize_date(s):
    if not s: return None
    m = re.match(r'(\d{4})-(\d{2})-(\d{2})', str(s))
    if m: return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    # Try "May 15, 2026" format
    months = {'january':1,'february':2,'march':3,'april':4,'may':5,'june':6,
              'july':7,'august':8,'september':9,'october':10,'november':11,'december':12}
    m2 = re.search(r'(\w+)\s+(\d{1,2}),?\s+(\d{4})', str(s), re.I)
    if m2:
        mon = months.get(m2.group(1).lower())
        if mon:
            return f"{m2.group(3)}-{str(mon).zfill(2)}-{m2.group(2).zfill(2)}"
    return None

def extract_time(s):
    if not s: return ""
    m = re.search(r'\b(\d{1,2}:\d{2}\s?(?:AM|PM|am|pm))', str(s))
    return m.group(1).strip() if m else ""


# ─────────────────────────────────────────────
# 1. ROAD AMERICA — Hardcoded 2026 Season
# ─────────────────────────────────────────────
def scrape_road_america():
    print("Loading Road America 2026 season schedule...")
    events = []

    # Full 2026 season — hardcoded from official schedule
    ROAD_AMERICA_EVENTS = [
        {
            "title": "Spring Vintage Weekend with SVRA",
            "date": "2026-05-15", "end_date": "2026-05-17",
            "start_time": "7:00 AM", "end_time": "5:00 PM",
            "description": "Classic racecars celebrate motorsport's rich heritage. Features '50s–'70s sports cars, Formula 5000, Formula Ford, Lotus, Alfa Romeo, Jaguar, Porsche, and Corvette. Season opener at Road America.",
            "link": "https://www.roadamerica.com/events/spring-vintage-weekend",
            "featured": True
        },
        {
            "title": "MotoAmerica Superbikes & Vintage MotoFest",
            "date": "2026-05-29", "end_date": "2026-05-31",
            "start_time": "8:00 AM",
            "description": "MotoAmerica Superbike races return to Road America with thrilling motorcycle competition and a family-friendly Vintage Motorcycle festival.",
            "link": "https://www.roadamerica.com/events/motoamerica",
            "featured": True
        },
        {
            "title": "WeatherTech Chicago Region SCCA June Sprints",
            "date": "2026-06-05", "end_date": "2026-06-07",
            "start_time": "8:00 AM",
            "description": "The 71st running of the June Sprints. Road America's longest-running event features grassroots SCCA road racing across multiple classes.",
            "link": "https://www.roadamerica.com/events/june-sprints",
            "featured": True
        },
        {
            "title": "XPEL INDYCAR Grand Prix presented by AMR",
            "date": "2026-06-18", "end_date": "2026-06-21",
            "start_time": "8:00 AM",
            "description": "IndyCar's premier open-wheel series returns to Road America with an international lineup of drivers on one of the world's most majestic road courses.",
            "link": "https://www.roadamerica.com/events/indycar-grand-prix",
            "featured": True
        },
        {
            "title": "Cheese Capital Cup featuring Trans Am SpeedTour",
            "date": "2026-06-26", "end_date": "2026-06-28",
            "start_time": "8:00 AM",
            "description": "Trans Am SpeedTour returns to Road America for a weekend of American road racing tradition.",
            "link": "https://www.roadamerica.com/events",
            "featured": True
        },
        {
            "title": "WeatherTech Vintage Weekend with Brian Redman",
            "date": "2026-07-16", "end_date": "2026-07-19",
            "start_time": "8:00 AM",
            "description": "One of the largest vintage racing events in the US. Features 400+ vintage and historic racecars, Dan Gurney Racing Eagles reunion, and a 60th anniversary Trans Am tribute.",
            "link": "https://www.roadamerica.com/events/vintage-weekend",
            "featured": True
        },
        {
            "title": "Motul SportsCar Endurance Grand Prix featuring IMSA",
            "date": "2026-07-30", "end_date": "2026-08-02",
            "start_time": "8:00 AM",
            "description": "A six-hour endurance event featuring IMSA's elite sportscars from nearly 20 manufacturers including Mercedes, Ferrari, Chevrolet, and Aston Martin.",
            "link": "https://www.roadamerica.com/events/imsa",
            "featured": True
        },
        {
            "title": "GT World Challenge America",
            "date": "2026-08-28", "end_date": "2026-08-30",
            "start_time": "8:00 AM",
            "description": "All-sportscar weekend at Road America featuring GT World Challenge America racing.",
            "link": "https://www.roadamerica.com/events/gt-world-challenge",
            "featured": True
        },
        {
            "title": "Art on Wheels Weekend with VSCDA",
            "date": "2026-09-18", "end_date": "2026-09-20",
            "start_time": "8:00 AM",
            "description": "300+ meticulously restored vintage and historic race cars spanning 11 racing classes. A three-day journey through automotive history.",
            "link": "https://www.roadamerica.com/events/vscda",
            "featured": True
        },
        {
            "title": "SCCA National Championship Runoffs",
            "date": "2026-10-01", "end_date": "2026-10-04",
            "start_time": "8:00 AM",
            "description": "The pinnacle of US amateur road racing. Top SCCA racers from across the country compete for national championships at Road America.",
            "link": "https://www.roadamerica.com/events/scca-runoffs",
            "featured": True
        },
        # Track Days (recurring)
        {
            "title": "Road America Track Day",
            "date": "2026-05-18", "start_time": "7:30 AM", "end_time": "5:00 PM",
            "description": "Drive your own street performance or track-prepared car at Road America in a fun, safe, non-competitive environment on the full 4-mile circuit.",
            "link": "https://www.roadamerica.com/track-days"
        },
        {
            "title": "Road America Track Day",
            "date": "2026-06-29", "start_time": "7:30 AM", "end_time": "5:00 PM",
            "description": "Drive your own street performance or track-prepared car at Road America in a fun, safe, non-competitive environment on the full 4-mile circuit.",
            "link": "https://www.roadamerica.com/track-days"
        },
        {
            "title": "Road America Track Day",
            "date": "2026-07-09", "start_time": "7:30 AM", "end_time": "5:00 PM",
            "description": "Drive your own street performance or track-prepared car at Road America in a fun, safe, non-competitive environment.",
            "link": "https://www.roadamerica.com/track-days"
        },
        {
            "title": "Road America Track Day",
            "date": "2026-08-20", "start_time": "7:30 AM", "end_time": "5:00 PM",
            "description": "Drive your own street performance or track-prepared car at Road America in a fun, safe, non-competitive environment.",
            "link": "https://www.roadamerica.com/track-days"
        },
        {
            "title": "Road America Track Day",
            "date": "2026-10-08", "start_time": "7:30 AM", "end_time": "5:00 PM",
            "description": "Drive your own street performance or track-prepared car at Road America in a fun, safe, non-competitive environment.",
            "link": "https://www.roadamerica.com/track-days"
        },
        # Sunset Cruises (Mon/Wed evenings May–Aug)
        {
            "title": "Sunset Cruise at Road America",
            "date": "2026-05-18", "start_time": "6:00 PM", "end_time": "8:00 PM",
            "recurrence": "weekly_multiple", "recurrence_days": "Monday,Wednesday",
            "end_date": "2026-08-19",
            "description": "Leisurely 3-lap sunset cruise of the iconic 4-mile Road America track in your own vehicle. Mon & Wed evenings May through August.",
            "link": "https://www.roadamerica.com/get-track"
        },
        # Farmers Market
        {
            "title": "Elkhart Lake Farmers & Artisans Market",
            "date": "2026-05-16", "start_time": "8:00 AM", "end_time": "12:00 PM",
            "recurrence": "weekly", "recurrence_day": "Saturday",
            "end_date": "2026-10-31",
            "description": "Saturday morning tradition in the Village Square. Fresh vegetables, flowers, cheeses, local arts and specialty products from ~50 vendors.",
            "link": "https://www.elkhartlake.com/events/"
        },
    ]

    today = datetime.now().strftime("%Y-%m-%d")
    for e in ROAD_AMERICA_EVENTS:
        if e.get("end_date", e["date"]) >= today:
            event = {
                "title": e["title"],
                "date": e["date"],
                "description": e.get("description", ""),
                "location": "Road America, N7390 US-12, Elkhart Lake, WI 53020",
                "link": e.get("link", "https://www.roadamerica.com"),
                "source": "Road America",
                "source_url": "https://www.roadamerica.com",
                "lat": 43.7969, "lng": -87.9897,
                "scraped_at": datetime.now().isoformat()
            }
            if e.get("start_time"): event["start_time"] = e["start_time"]
            if e.get("end_time"): event["end_time"] = e["end_time"]
            if e.get("end_date"): event["end_date"] = e["end_date"]
            if e.get("recurrence"): event["recurrence"] = e["recurrence"]
            if e.get("recurrence_day"): event["recurrence_day"] = e["recurrence_day"]
            if e.get("recurrence_days"): event["recurrence_days"] = e["recurrence_days"]
            if e.get("featured"): event["featured"] = True
            events.append(event)

    print(f"  Loaded {len(events)} Road America events")
    return events


# ─────────────────────────────────────────────
# 1b. ELKHARTLAKE.COM — Known Annual Events
# (hardcoded since site blocks scrapers)
# ─────────────────────────────────────────────
def scrape_elkhartlake_known():
    print("Loading known elkhartlake.com annual events...")
    events = []
    today = datetime.now().strftime("%Y-%m-%d")

    KNOWN_EVENTS = [
        # ── Osthoff Resort ──
        {
            "title": "Jazz on the Vine",
            "date": "2026-05-01", "end_date": "2026-05-02",
            "start_time": "7:00 PM",
            "description": "Spectacular live music celebration at The Osthoff Resort featuring world-class jazz artists. Pairs intimate performances with the elegance of a AAA Four-Diamond resort.",
            "location": "The Osthoff Resort, 101 Osthoff Ave, Elkhart Lake, WI",
            "link": "https://www.elkhartlake.com/event/jazz-on-the-vine/",
            "featured": True
        },
        {
            "title": "Jazz on the Vine — Weekend 2",
            "date": "2026-05-08", "end_date": "2026-05-09",
            "start_time": "7:00 PM",
            "description": "Second weekend of Jazz on the Vine at The Osthoff Resort. Live jazz performances with acclaimed artists in an intimate lakeside setting.",
            "location": "The Osthoff Resort, 101 Osthoff Ave, Elkhart Lake, WI",
            "link": "https://www.elkhartlake.com/event/jazz-on-the-vine/",
        },
        {
            "title": "Jazz on the Vine — Weekend 3",
            "date": "2026-05-15", "end_date": "2026-05-16",
            "start_time": "7:00 PM",
            "description": "Third weekend of Jazz on the Vine at The Osthoff Resort.",
            "location": "The Osthoff Resort, 101 Osthoff Ave, Elkhart Lake, WI",
            "link": "https://www.elkhartlake.com/event/jazz-on-the-vine/",
        },
        # ── Village Events ──
        {
            "title": "Shop & Sip Elkhart Lake",
            "date": "2026-05-16",
            "start_time": "11:00 AM", "end_time": "4:00 PM",
            "description": "The 10th Annual Shop & Sip! Visit downtown Elkhart Lake shops and restaurants for a day of shopping, tastings, and community fun.",
            "location": "Downtown Elkhart Lake, WI",
            "link": "https://www.elkhartlake.com/event/shop-sip-elkhart-lake/",
            "featured": True
        },
        {
            "title": "Elkhart Lake Annual Veterans Memorial Tribute",
            "date": "2026-05-23",
            "start_time": "10:00 AM",
            "description": "Annual ceremony honoring veterans at the Elkhart Lake Veterans Memorial.",
            "location": "Veterans Memorial, Elkhart Lake, WI",
            "link": "https://www.elkhartlake.com/events/",
        },
        {
            "title": "4 Miles of Fitness",
            "date": "2026-05-13",
            "start_time": "7:00 AM",
            "description": "Bike, walk, or run your way around Road America's legendary 4-mile, 14-turn road course. A fan-favorite fitness event set against the scenic 640-acre property.",
            "location": "Road America, N7390 US-12, Elkhart Lake, WI",
            "link": "https://www.elkhartlake.com/event/4-miles-of-fitness/",
        },
        {
            "title": "Elkhart Lake Fireman's Picnic — Friday Night",
            "date": "2026-07-03",
            "start_time": "7:30 PM",
            "description": "Annual 4th of July celebration with the Elkhart Lake Fire Department. Live music, food, drinks, and fireworks at dusk.",
            "location": "Elkhart Lake, WI",
            "link": "https://www.elkhartlake.com/event/elkhart-lake-firemans-picnic/",
            "featured": True
        },
        {
            "title": "Elkhart Lake Fireman's Picnic — Sunday",
            "date": "2026-07-05",
            "start_time": "11:30 AM",
            "description": "Fireman's Parade at 11:30am in downtown Elkhart Lake followed by live music 1:30-5pm.",
            "location": "Downtown Elkhart Lake, WI",
            "link": "https://www.elkhartlake.com/event/elkhart-lake-firemans-picnic/",
        },
        {
            "title": "Road America Concours d'Elegance",
            "date": "2026-07-17", "end_date": "2026-07-18",
            "start_time": "6:00 PM", "end_time": "8:00 PM",
            "description": "Spectacular display of vintage racecars and luxury sports cars in downtown Elkhart Lake. Friday features a parade of vintage racecars; Saturday features luxury sports cars.",
            "location": "Downtown Elkhart Lake, WI",
            "link": "https://www.elkhartlake.com/event/weathertech-vintage-weekend-with-brian-redman/",
            "featured": True
        },
        {
            "title": "Elktoberfest",
            "date": "2026-09-19",
            "start_time": "10:00 AM",
            "description": "Bavarian fun with stein hoists, brats, pretzels, polka, and gemütlichkeit. Features the Elktoberfest Run/Walk, family games, and live music from Boo! The Band at Siebkens.",
            "location": "Downtown Elkhart Lake, WI",
            "link": "https://www.elkhartlake.com/event/elktoberfest/",
            "featured": True
        },
        # ── Siebkens Named Concerts ──
        {
            "title": "Siebkens Live Music — Kylar Kuzio",
            "date": "2026-05-15",
            "start_time": "7:00 PM",
            "description": "Welcome back, Kylar Kuzio! Live music at Siebkens Resort kicking off the summer season. Outdoor bandstand outside the Stop-Inn Tavern. Free, family and dog friendly.",
            "location": "Siebkens Resort, 284 S Lake St, Elkhart Lake, WI",
            "link": "https://www.elkhartlake.com/event/siebkens-live-music-by-kylar-kuzio/",
            "featured": True
        },
        {
            "title": "Siebkens Live Music — Wire & Nail",
            "date": "2026-06-19",
            "start_time": "7:00 PM",
            "description": "Milwaukee's #1 honky tonk, rock and roll band hits the stage for IndyCar Weekend. High-energy sound with classic country and rock influences. Bandstand outside the Stop-Inn Tavern.",
            "location": "Siebkens Resort, 284 S Lake St, Elkhart Lake, WI",
            "link": "https://www.elkhartlake.com/event/siebkens-live-music-by-wire-nail-2/",
            "featured": True
        },
        {
            "title": "Siebkens Live Music — 7000apart",
            "date": "2026-07-01",
            "start_time": "7:00 PM",
            "recurrence": "weekly", "recurrence_day": "Wednesday",
            "end_date": "2026-08-26",
            "description": "7000apart returns to Siebkens Summer Concert Series on Wednesday nights. Live music on the bandstand outside the Stop-Inn Tavern. Free, family & dog friendly.",
            "location": "Siebkens Resort, 284 S Lake St, Elkhart Lake, WI",
            "link": "https://www.elkhartlake.com/event/siebkens-live-music-by-7000apart/",
        },
        {
            "title": "Siebkens Block Party",
            "date": "2026-07-11",
            "start_time": "11:00 AM",
            "description": "Annual Siebkens Block Party — 3 live bands, lawn games, local vendors, and a tasting by Fifth Ward Brewing Company. Stop-Inn Tavern open 11am–10pm.",
            "location": "Siebkens Resort, 284 S Lake St, Elkhart Lake, WI",
            "link": "https://www.elkhartlake.com/event/siebkens-block-party/",
            "featured": True
        },
        {
            "title": "Siebkens Live Music — Chili Dogs",
            "date": "2026-07-18",
            "start_time": "7:00 PM",
            "description": "Chili Dogs take the stage at Siebkens for a night of rock at the Summer Concert Series. Bandstand outside the Stop-Inn Tavern.",
            "location": "Siebkens Resort, 284 S Lake St, Elkhart Lake, WI",
            "link": "https://www.elkhartlake.com/events/month/2026-07/",
        },
        {
            "title": "Live Music at Siebkens",
            "date": "2026-05-15", "start_time": "7:00 PM",
            "recurrence": "weekly", "recurrence_day": "Friday",
            "end_date": "2026-10-02",
            "description": "Live music at the legendary Siebkens Resort on the shores of Elkhart Lake. A tradition since 1916.",
            "location": "Siebkens Resort, 284 S Lake St, Elkhart Lake, WI",
            "link": "https://www.siebkens.com/events/",
        },
        {
            "title": "Live Music at Siebkens",
            "date": "2026-05-16", "start_time": "7:00 PM",
            "recurrence": "weekly", "recurrence_day": "Saturday",
            "end_date": "2026-10-03",
            "description": "Live music at the legendary Siebkens Resort on the shores of Elkhart Lake.",
            "location": "Siebkens Resort, 284 S Lake St, Elkhart Lake, WI",
            "link": "https://www.siebkens.com/events/",
        },
        # ── Osthoff recurring ──
        {
            "title": "Live Music at The Osthoff — The Elk Room",
            "date": "2026-05-15", "start_time": "7:00 PM",
            "recurrence": "weekly", "recurrence_day": "Friday",
            "end_date": "2026-09-25",
            "description": "Live music in The Elk Room at The Osthoff Resort. Kick back, enjoy a drink, and let the music create the perfect backdrop for a lakeside evening.",
            "location": "The Osthoff Resort, 101 Osthoff Ave, Elkhart Lake, WI",
            "link": "https://www.elkhartlake.com/events/",
        },
        {
            "title": "Live Music at The Osthoff — The Elk Room",
            "date": "2026-05-16", "start_time": "7:00 PM",
            "recurrence": "weekly", "recurrence_day": "Saturday",
            "end_date": "2026-09-26",
            "description": "Live music in The Elk Room at The Osthoff Resort.",
            "location": "The Osthoff Resort, 101 Osthoff Ave, Elkhart Lake, WI",
            "link": "https://www.elkhartlake.com/events/",
        },
        # ── Lions Club ──
        {
            "title": "Elkhart Lake Lions Club Brat Fry",
            "date": "2026-05-23",
            "start_time": "10:00 AM", "end_time": "1:30 PM",
            "description": "Community brat fry hosted by the Elkhart Lake Lions Club.",
            "location": "Elkhart Lake, WI",
            "link": "https://www.elkhartlake.com/events/",
        },
    ]

    for e in KNOWN_EVENTS:
        if e.get("end_date", e["date"]) >= today:
            event = {
                "title": e["title"],
                "date": e["date"],
                "description": e.get("description", ""),
                "location": e.get("location", "Elkhart Lake, WI"),
                "link": e.get("link", "https://www.elkhartlake.com/events/"),
                "source": "Elkhart Lake Tourism",
                "source_url": "https://www.elkhartlake.com/events/",
                "scraped_at": datetime.now().isoformat()
            }
            if e.get("start_time"): event["start_time"] = e["start_time"]
            if e.get("end_time"): event["end_time"] = e["end_time"]
            if e.get("end_date"): event["end_date"] = e["end_date"]
            if e.get("recurrence"): event["recurrence"] = e["recurrence"]
            if e.get("recurrence_day"): event["recurrence_day"] = e["recurrence_day"]
            if e.get("featured"): event["featured"] = True
            events.append(event)

    print(f"  Loaded {len(events)} known elkhartlake.com events")
    return events


# ─────────────────────────────────────────────
# 2. ELKHARTLAKE.COM — Official Tourism Site
# ─────────────────────────────────────────────
def scrape_elkhartlake_com():
    print("Scraping elkhartlake.com events...")
    events = []
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.set_extra_http_headers({"User-Agent": HEADERS["User-Agent"]})

            for url in [
                "https://www.elkhartlake.com/events/",
                "https://www.elkhartlake.com/events/page/2/",
                "https://www.elkhartlake.com/events/page/3/",
            ]:
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=25000)
                    page.wait_for_timeout(3000)
                    html = page.content()
                    soup = BeautifulSoup(html, "html.parser")

                    # Tribe Events WordPress plugin selectors
                    containers = (
                        soup.find_all("article", class_=re.compile(r"tribe_events|tribe-events", re.I)) or
                        soup.find_all("div", class_=re.compile(r"tribe-event|type-tribe", re.I)) or
                        soup.find_all("article") or
                        soup.find_all("div", class_=re.compile(r"event-item|eventitem", re.I))
                    )

                    for c in containers:
                        try:
                            title_el = (c.find(class_=re.compile(r"tribe-event-url|tribe-events-list-event-title|entry-title", re.I)) or
                                       c.find("h2") or c.find("h3") or c.find("h4"))
                            if not title_el: continue
                            title = title_el.get_text(strip=True)
                            if len(title) < 3 or title.lower() in ["events", "calendar"]: continue

                            date_el = (c.find(class_=re.compile(r"tribe-event-date-start|tribe-events-schedule|tribe-event-time", re.I)) or
                                      c.find("time") or c.find(class_=re.compile(r"date|when|start", re.I)))
                            raw_date = ""
                            if date_el:
                                raw_date = date_el.get("datetime") or date_el.get_text(strip=True)
                            date = normalize_date(raw_date) or "See website"
                            start_time = extract_time(raw_date)

                            venue_el = c.find(class_=re.compile(r"tribe-venue|tribe-address|location", re.I))
                            location = venue_el.get_text(strip=True)[:80] if venue_el else "Elkhart Lake, WI"

                            desc_el = (c.find(class_=re.compile(r"tribe-events-list-event-description|entry-summary|excerpt", re.I)) or
                                      c.find("p"))
                            description = desc_el.get_text(strip=True)[:300] if desc_el else ""

                            link_el = c.find("a", href=True)
                            link = link_el["href"] if link_el else "https://www.elkhartlake.com/events/"
                            if link.startswith("/"): link = "https://www.elkhartlake.com" + link

                            event = {
                                "title": title, "date": date, "description": description,
                                "location": location or "Elkhart Lake, WI",
                                "link": link,
                                "source": "Elkhart Lake Tourism",
                                "source_url": "https://www.elkhartlake.com/events/",
                                "scraped_at": datetime.now().isoformat()
                            }
                            if start_time: event["start_time"] = start_time
                            events.append(event)
                        except: continue
                except Exception as page_err:
                    print(f"  Error on {url}: {page_err}")
                    continue
            browser.close()

        print(f"  Found {len(events)} events from elkhartlake.com")
    except Exception as e:
        print(f"  Error scraping elkhartlake.com: {e}")
    return events


# ─────────────────────────────────────────────
# 3. SIEBKENS RESORT — Live Music Calendar
# ─────────────────────────────────────────────
def scrape_siebkens():
    print("Scraping Siebkens Resort events...")
    events = []
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.set_extra_http_headers({"User-Agent": HEADERS["User-Agent"]})
            page.goto("https://www.siebkens.com/events/", wait_until="domcontentloaded", timeout=25000)
            page.wait_for_timeout(4000)
            html = page.content()
            browser.close()

        soup = BeautifulSoup(html, "html.parser")
        containers = (
            soup.find_all("article") or
            soup.find_all("div", class_=re.compile(r"event|tribe|card", re.I))
        )

        for c in containers:
            try:
                title_el = c.find("h2") or c.find("h3") or c.find("h4") or c.find(class_=re.compile(r"title", re.I))
                if not title_el: continue
                title = title_el.get_text(strip=True)
                if len(title) < 3: continue

                date_el = c.find(class_=re.compile(r"date|time|start", re.I)) or c.find("time") or c.find("abbr")
                raw_date = date_el.get_text(strip=True) if date_el else ""
                date = normalize_date(raw_date) or "See website"
                start_time = extract_time(raw_date)

                desc_el = c.find("p")
                description = desc_el.get_text(strip=True)[:300] if desc_el else "Live music at Siebkens Resort on the shores of Elkhart Lake."

                link_el = c.find("a", href=True)
                link = link_el["href"] if link_el else "https://www.siebkens.com/events/"
                if link.startswith("/"): link = "https://www.siebkens.com" + link

                event = {
                    "title": title, "date": date, "description": description,
                    "location": "Siebkens Resort, 284 S Lake St, Elkhart Lake, WI",
                    "link": link,
                    "source": "Siebkens Resort",
                    "source_url": "https://www.siebkens.com/events/",
                    "lat": 43.8336, "lng": -87.9717,
                    "scraped_at": datetime.now().isoformat()
                }
                if start_time: event["start_time"] = start_time
                events.append(event)
            except: continue

        print(f"  Found {len(events)} events from Siebkens")
    except Exception as e:
        print(f"  Error scraping Siebkens: {e}")
    return events


# ─────────────────────────────────────────────
# 4. VISIT SHEBOYGAN COUNTY — Elkhart Lake Events
# ─────────────────────────────────────────────
def scrape_visit_sheboygan():
    print("Scraping Visit Sheboygan County events...")
    events = []
    try:
        r = requests.get(
            "https://visitsheboygancounty.com/events/category/elkhart-lake/",
            headers=HEADERS, timeout=15
        )
        soup = BeautifulSoup(r.text, "html.parser")
        containers = (
            soup.find_all("article") or
            soup.find_all("div", class_=re.compile(r"event|card|tribe", re.I))
        )
        for c in containers:
            try:
                title_el = c.find("h2") or c.find("h3") or c.find("h4")
                if not title_el: continue
                title = title_el.get_text(strip=True)
                if len(title) < 3: continue

                date_el = c.find(class_=re.compile(r"date|time|start", re.I)) or c.find("time") or c.find("abbr")
                raw_date = date_el.get("datetime") or date_el.get_text(strip=True) if date_el else ""
                date = normalize_date(raw_date) or "See website"
                start_time = extract_time(raw_date)

                desc_el = c.find("p")
                description = desc_el.get_text(strip=True)[:300] if desc_el else ""

                link_el = c.find("a", href=True)
                link = link_el["href"] if link_el else "https://visitsheboygancounty.com/events/"
                if link.startswith("/"): link = "https://visitsheboygancounty.com" + link

                event = {
                    "title": title, "date": date, "description": description,
                    "location": "Elkhart Lake, WI",
                    "link": link,
                    "source": "Visit Sheboygan County",
                    "source_url": "https://visitsheboygancounty.com/events/category/elkhart-lake/",
                    "scraped_at": datetime.now().isoformat()
                }
                if start_time: event["start_time"] = start_time
                events.append(event)
            except: continue

        print(f"  Found {len(events)} events from Visit Sheboygan County")
    except Exception as e:
        print(f"  Error scraping Visit Sheboygan County: {e}")
    return events


# ─────────────────────────────────────────────
# 5. OSTHOFF RESORT — Events & Dining
# ─────────────────────────────────────────────
def scrape_osthoff():
    print("Scraping Osthoff Resort events...")
    events = []
    try:
        r = requests.get("https://www.osthoff.com/events/", headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        containers = (
            soup.find_all("article") or
            soup.find_all("div", class_=re.compile(r"event|card|listing", re.I))
        )
        for c in containers:
            try:
                title_el = c.find("h2") or c.find("h3") or c.find("h4")
                if not title_el: continue
                title = title_el.get_text(strip=True)
                if len(title) < 3: continue

                date_el = c.find(class_=re.compile(r"date|time", re.I)) or c.find("time")
                raw_date = date_el.get_text(strip=True) if date_el else ""
                date = normalize_date(raw_date) or "See website"
                start_time = extract_time(raw_date)

                desc_el = c.find("p")
                description = desc_el.get_text(strip=True)[:300] if desc_el else ""

                link_el = c.find("a", href=True)
                link = link_el["href"] if link_el else "https://www.osthoff.com/events/"
                if link.startswith("/"): link = "https://www.osthoff.com" + link

                event = {
                    "title": title, "date": date, "description": description,
                    "location": "Osthoff Resort, 101 Osthoff Ave, Elkhart Lake, WI",
                    "link": link,
                    "source": "Osthoff Resort",
                    "source_url": "https://www.osthoff.com/events/",
                    "lat": 43.8347, "lng": -87.9692,
                    "scraped_at": datetime.now().isoformat()
                }
                if start_time: event["start_time"] = start_time
                events.append(event)
            except: continue

        print(f"  Found {len(events)} events from Osthoff Resort")
    except Exception as e:
        print(f"  Error scraping Osthoff: {e}")
    return events


# ─────────────────────────────────────────────
# 6. VILLAGE OF ELKHART LAKE — Official Calendar
# ─────────────────────────────────────────────
def scrape_village_calendar():
    print("Scraping Village of Elkhart Lake calendar...")
    events = []
    try:
        r = requests.get("https://elkhartlakewi.gov/calendar/", headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        containers = (
            soup.find_all("article") or
            soup.find_all("div", class_=re.compile(r"event|tribe|calendar", re.I)) or
            soup.find_all("li", class_=re.compile(r"event", re.I))
        )
        for c in containers:
            try:
                title_el = c.find("h2") or c.find("h3") or c.find("h4") or c.find(class_=re.compile(r"title", re.I))
                if not title_el: continue
                title = title_el.get_text(strip=True)
                if len(title) < 3: continue

                date_el = c.find(class_=re.compile(r"date|time|start", re.I)) or c.find("time") or c.find("abbr")
                raw_date = date_el.get("datetime") or date_el.get_text(strip=True) if date_el else ""
                date = normalize_date(raw_date) or "See website"
                start_time = extract_time(raw_date)

                link_el = c.find("a", href=True)
                link = link_el["href"] if link_el else "https://elkhartlakewi.gov/calendar/"
                if link.startswith("/"): link = "https://elkhartlakewi.gov" + link

                event = {
                    "title": title, "date": date, "description": "",
                    "location": "Elkhart Lake, WI",
                    "link": link,
                    "source": "Village of Elkhart Lake",
                    "source_url": "https://elkhartlakewi.gov/calendar/",
                    "scraped_at": datetime.now().isoformat()
                }
                if start_time: event["start_time"] = start_time
                events.append(event)
            except: continue

        print(f"  Found {len(events)} events from Village calendar")
    except Exception as e:
        print(f"  Error scraping Village calendar: {e}")
    return events


# ─────────────────────────────────────────────
# 7. SERPAPI — Google Events for Elkhart Lake
# ─────────────────────────────────────────────
def scrape_google_events():
    print("Scraping Google Events via SerpApi...")
    events = []

    queries = [
        "events in Elkhart Lake Wisconsin 2026",
        "Road America events 2026",
        "Osthoff Resort events 2026",
        "Siebkens Resort live music 2026",
        "things to do Elkhart Lake Wisconsin this weekend",
        "Sheboygan County Wisconsin events 2026",
        "elkhartlake.com events",
        "Elkhart Lake festival 2026",
    ]

    seen = set()
    today = datetime.now().strftime("%Y-%m-%d")

    for query in queries:
        try:
            params = {
                "engine": "google_events",
                "q": query,
                "location": "Elkhart Lake, Wisconsin, United States",
                "gl": "us", "hl": "en",
                "api_key": SERPAPI_KEY
            }
            r = requests.get("https://serpapi.com/search", params=params, timeout=15)
            if r.status_code != 200:
                print(f"  SerpApi error {r.status_code} for '{query}'")
                continue

            results = r.json().get("events_results", [])
            print(f"  '{query}': {len(results)} events")

            for item in results:
                try:
                    title = item.get("title", "").strip()
                    if not title or len(title) < 3: continue
                    key = title.lower()[:40]
                    if key in seen: continue
                    seen.add(key)

                    date_info = item.get("date", {})
                    when = date_info.get("when", "")
                    start_date = date_info.get("start_date", "")
                    date = normalize_date(start_date) or normalize_date(when) or "See website"
                    start_time = extract_time(when)

                    address = item.get("address", [])
                    location = ", ".join(address) if isinstance(address, list) else str(address) or "Elkhart Lake, WI"

                    link = item.get("link", "")
                    ticket_info = item.get("ticket_info", [])
                    if ticket_info and isinstance(ticket_info, list):
                        link = ticket_info[0].get("link", link)

                    description = item.get("description", "")
                    is_free = True if "free" in description.lower() or "free" in title.lower() else (False if ticket_info else None)

                    event = {
                        "title": title, "date": date,
                        "description": description[:300],
                        "location": location or "Elkhart Lake, WI",
                        "link": link or f"https://www.google.com/search?q={title.replace(' ','+')}",
                        "source": "Google Events",
                        "source_url": "https://www.google.com",
                        "is_free": is_free,
                        "scraped_at": datetime.now().isoformat()
                    }
                    if start_time: event["start_time"] = start_time
                    events.append(event)
                except: continue

        except Exception as e:
            print(f"  SerpApi error for '{query}': {e}")
            continue

    print(f"  Found {len(events)} unique events from Google Events")
    return events


# ─────────────────────────────────────────────
# 8. EVENTBRITE — Elkhart Lake Events
# ─────────────────────────────────────────────
def scrape_eventbrite():
    print("Scraping Eventbrite for Elkhart Lake events...")
    events = []
    try:
        r = requests.get(
            "https://www.eventbrite.com/d/wi--elkhart-lake/events/",
            headers=HEADERS, timeout=15
        )
        soup = BeautifulSoup(r.text, "html.parser")
        containers = soup.find_all("div", class_=re.compile(r"search-event-card|event-card", re.I))

        for c in containers:
            try:
                title_el = c.find(class_=re.compile(r"event-title|card-title", re.I)) or c.find("h2") or c.find("h3")
                if not title_el: continue
                title = title_el.get_text(strip=True)
                if len(title) < 3: continue

                date_el = c.find(class_=re.compile(r"event-date|card-date|date", re.I)) or c.find("time")
                raw_date = date_el.get("datetime") or date_el.get_text(strip=True) if date_el else ""
                date = normalize_date(raw_date) or "See website"
                start_time = extract_time(raw_date)

                location_el = c.find(class_=re.compile(r"location|venue", re.I))
                location = location_el.get_text(strip=True)[:80] if location_el else "Elkhart Lake, WI"

                link_el = c.find("a", href=True)
                link = link_el["href"] if link_el else "https://www.eventbrite.com/d/wi--elkhart-lake/events/"

                event = {
                    "title": title, "date": date, "description": "",
                    "location": location,
                    "link": link,
                    "source": "Eventbrite",
                    "source_url": "https://www.eventbrite.com/d/wi--elkhart-lake/events/",
                    "scraped_at": datetime.now().isoformat()
                }
                if start_time: event["start_time"] = start_time
                events.append(event)
            except: continue

        print(f"  Found {len(events)} events from Eventbrite")
    except Exception as e:
        print(f"  Error scraping Eventbrite: {e}")
    return events


# ─────────────────────────────────────────────
# 9. ALLEVENTS.IN — Elkhart Lake Music Events
# ─────────────────────────────────────────────
def scrape_allevents():
    print("Scraping allevents.in for Elkhart Lake events...")
    events = []
    try:
        import requests
        from bs4 import BeautifulSoup

        urls = [
            "https://allevents.in/elkhart-lake/music",
            "https://allevents.in/elkhart-lake/all",
        ]
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        seen_titles = set()
        for url in urls:
            r = requests.get(url, headers=headers, timeout=15)
            if r.status_code != 200:
                print(f"  allevents.in returned {r.status_code}")
                continue
            soup = BeautifulSoup(r.text, "html.parser")
            containers = (
                soup.find_all("li", class_=re.compile(r"event-item|item", re.I)) or
                soup.find_all("div", class_=re.compile(r"event-item|card|event-card", re.I))
            )
            for c in containers:
                try:
                    title_el = c.find("h3") or c.find("h2") or c.find(class_=re.compile(r"title|name", re.I))
                    if not title_el: continue
                    title = title_el.get_text(strip=True)
                    if len(title) < 3: continue
                    if title.lower() in seen_titles: continue
                    seen_titles.add(title.lower())

                    date_el = c.find(class_=re.compile(r"date|time|when", re.I)) or c.find("time")
                    raw_date = date_el.get("datetime") or date_el.get_text(strip=True) if date_el else ""
                    date = normalize_date(raw_date) or "See website"
                    start_time = extract_time(raw_date)

                    location_el = c.find(class_=re.compile(r"location|venue|place", re.I))
                    location = location_el.get_text(strip=True)[:80] if location_el else "Elkhart Lake, WI"

                    link_el = c.find("a", href=True)
                    link = link_el["href"] if link_el else url

                    event = {
                        "title": title, "date": date, "description": "",
                        "location": location or "Elkhart Lake, WI",
                        "link": link,
                        "source": "Elkhart Lake Tourism",
                        "source_url": "https://allevents.in/elkhart-lake/all",
                        "scraped_at": datetime.now().isoformat()
                    }
                    if start_time: event["start_time"] = start_time
                    events.append(event)
                except: continue

        print(f"  Found {len(events)} events from allevents.in")
    except Exception as e:
        print(f"  Error scraping allevents.in: {e}")
    return events


# ─────────────────────────────────────────────
# 10. OSTHOFF.COM — Events Calendar
# (direct scrape of their own calendar)
# ─────────────────────────────────────────────
def scrape_osthoff_calendar():
    print("Scraping Osthoff Resort calendar...")
    events = []
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.set_extra_http_headers({"User-Agent": HEADERS["User-Agent"]})
            page.goto("https://osthoff.com/events/", wait_until="networkidle", timeout=25000)
            page.wait_for_timeout(4000)
            html = page.content()
            browser.close()

        soup = BeautifulSoup(html, "html.parser")
        containers = (
            soup.find_all("article", class_=re.compile(r"tribe_events|tribe-events|event", re.I)) or
            soup.find_all("div", class_=re.compile(r"tribe-event|event-item", re.I)) or
            soup.find_all("article")
        )
        for c in containers:
            try:
                title_el = c.find(class_=re.compile(r"tribe-event|entry-title|event-title", re.I)) or c.find("h2") or c.find("h3")
                if not title_el: continue
                title = title_el.get_text(strip=True)
                if len(title) < 3: continue

                date_el = (c.find(class_=re.compile(r"tribe-event-date|tribe-events-schedule|start", re.I)) or
                           c.find("time") or c.find(class_=re.compile(r"date", re.I)))
                raw_date = date_el.get("datetime") or date_el.get_text(strip=True) if date_el else ""
                date = normalize_date(raw_date) or "See website"
                start_time = extract_time(raw_date)

                link_el = c.find("a", href=True)
                link = link_el["href"] if link_el else "https://osthoff.com/events/"
                if link.startswith("/"): link = "https://osthoff.com" + link

                desc_el = c.find("p")
                description = desc_el.get_text(strip=True)[:300] if desc_el else ""

                event = {
                    "title": title, "date": date, "description": description,
                    "location": "The Osthoff Resort, 101 Osthoff Ave, Elkhart Lake, WI",
                    "link": link,
                    "source": "Elkhart Lake Tourism",
                    "source_url": "https://osthoff.com/events/",
                    "lat": 43.8347, "lng": -87.9692,
                    "scraped_at": datetime.now().isoformat()
                }
                if start_time: event["start_time"] = start_time
                events.append(event)
            except: continue

        print(f"  Found {len(events)} events from Osthoff calendar")
    except Exception as e:
        print(f"  Error scraping Osthoff calendar: {e}")
    return events


# ─────────────────────────────────────────────
# DEDUP & SAVE
# ─────────────────────────────────────────────
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

def save_events(events, filename="events-elkhartlake.json"):
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
def main():
    print("=" * 55)
    print("  Yoocal Elkhart Lake Scraper")
    print("=" * 55)
    print()

    all_events = []
    all_events += scrape_road_america()
    all_events += scrape_elkhartlake_known()
    all_events += scrape_elkhartlake_com()
    all_events += scrape_siebkens()
    all_events += scrape_visit_sheboygan()
    all_events += scrape_osthoff()
    all_events += scrape_village_calendar()
    all_events += scrape_google_events()
    all_events += scrape_eventbrite()
    all_events += scrape_allevents()
    all_events += scrape_osthoff_calendar()

    print(f"\nTotal raw events: {len(all_events)}")
    unique = deduplicate(all_events)
    print(f"After deduplication: {len(unique)}")

    save_events(unique)

    print("\nDone! Sample events:")
    for e in unique[:10]:
        print(f"  [{e['source']}] {e['title']} -- {e['date']} {e.get('start_time','')}")

if __name__ == "__main__":
    main()

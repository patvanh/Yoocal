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
from event_classifier import classify_events
import re
import os
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone

# Mountain Time for today_iso filtering
MOUNTAIN = timezone(timedelta(hours=-6))

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

SERPAPI_KEY = os.environ.get("SERPAPI_KEY", "")

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
            "link": "https://www.roadamerica.com/spring-vintage-weekend-svra",
            "featured": True
        },
        {
            "title": "MotoAmerica Superbikes & Vintage MotoFest",
            "date": "2026-05-29", "end_date": "2026-05-31",
            "start_time": "8:00 AM",
            "description": "MotoAmerica Superbike races return to Road America with thrilling motorcycle competition and a family-friendly Vintage Motorcycle festival.",
            "link": "https://www.roadamerica.com/motoamerica-superbikes-vintage-motofest",
            "featured": True
        },
        {
            "title": "WeatherTech Chicago Region SCCA June Sprints",
            "date": "2026-06-05", "end_date": "2026-06-07",
            "start_time": "8:00 AM",
            "description": "The 71st running of the June Sprints. Road America's longest-running event features grassroots SCCA road racing across multiple classes.",
            "link": "https://www.roadamerica.com/weathertech-chicago-region-scca-june-sprints",
            "featured": True
        },
        {
            "title": "XPEL INDYCAR Grand Prix presented by AMR",
            "date": "2026-06-18", "end_date": "2026-06-21",
            "start_time": "8:00 AM",
            "description": "IndyCar's premier open-wheel series returns to Road America with an international lineup of drivers on one of the world's most majestic road courses.",
            "link": "https://www.roadamerica.com/events",
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
            "link": "https://www.roadamerica.com/weathertech-vintage-weekend-brian-redman",
            "featured": True
        },
        {
            "title": "Motul SportsCar Endurance Grand Prix featuring IMSA",
            "date": "2026-07-30", "end_date": "2026-08-02",
            "start_time": "8:00 AM",
            "description": "A six-hour endurance event featuring IMSA's elite sportscars from nearly 20 manufacturers including Mercedes, Ferrari, Chevrolet, and Aston Martin.",
            "link": "https://www.roadamerica.com/motul-sportscar-endurance-grand-prix-featuring-imsa",
            "featured": True
        },
        {
            "title": "GT World Challenge America",
            "date": "2026-08-28", "end_date": "2026-08-30",
            "start_time": "8:00 AM",
            "description": "All-sportscar weekend at Road America featuring GT World Challenge America racing.",
            "link": "https://www.roadamerica.com/events",
            "featured": True
        },
        {
            "title": "Art on Wheels Weekend with VSCDA",
            "date": "2026-09-18", "end_date": "2026-09-20",
            "start_time": "8:00 AM",
            "description": "300+ meticulously restored vintage and historic race cars spanning 11 racing classes. A three-day journey through automotive history.",
            "link": "https://www.roadamerica.com/art-wheels-vintage-weekend-vscda",
            "featured": True
        },
        {
            "title": "SCCA National Championship Runoffs",
            "date": "2026-10-01", "end_date": "2026-10-04",
            "start_time": "8:00 AM",
            "description": "The pinnacle of US amateur road racing. Top SCCA racers from across the country compete for national championships at Road America.",
            "link": "https://www.roadamerica.com/events",
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
def scrape_siebkens_known():
    """Siebkens 2026 Summer Concert Series — browser-scraped from siebkens.com on 2026-05-13"""
    print("Loading Siebkens known concert events...")
    events = []
    today = datetime.now().strftime("%Y-%m-%d")

    CONCERTS = [
        {"title": "Siebkens Summer Concert: Kylar Kuzio", "date": "2026-05-27", "start_time": "7:00 PM", "end_time": "10:00 PM", "link": "https://www.siebkens.com/event/siebkens-summer-concert-series-kylar-kuzio-5/"},
        {"title": "Siebkens Live Music: Jeremiah Jams (MotoAmerica Wknd)", "date": "2026-05-29", "start_time": "7:00 PM", "end_time": "11:00 PM", "link": "https://www.siebkens.com/event/siebkens-summer-concert-series-jeremiah-jams-2/"},
        {"title": "Siebkens Live Music: Dave Steffen Band (MotoAmerica Wknd)", "date": "2026-05-30", "start_time": "7:30 PM", "end_time": "11:00 PM", "link": "https://www.siebkens.com/event/siebkens-summer-concert-series-dave-steffan-band/"},
        {"title": "Siebkens Summer Concert: Lilie", "date": "2026-06-03", "start_time": "7:00 PM", "end_time": "10:00 PM", "link": "https://www.siebkens.com/event/siebkens-summer-concert-series-lilie-3/"},
        {"title": "Siebkens Summer Concert: Chasing Tales", "date": "2026-06-10", "start_time": "7:00 PM", "end_time": "10:00 PM", "link": "https://www.siebkens.com/event/siebkens-summer-concert-series-chasing-tales-2/"},
        {"title": "Siebkens Summer Concert: 7000apart", "date": "2026-06-17", "start_time": "7:00 PM", "end_time": "10:00 PM", "link": "https://www.siebkens.com/event/siebkens-summer-concert-series-7000apart-5/"},
        {"title": "Siebkens Live Music: Wire & Nail (IndyCar Wknd)", "date": "2026-06-18", "start_time": "6:00 PM", "end_time": "10:00 PM", "link": "https://www.siebkens.com/event/siebkens-summer-concert-series-wire-nail-4/", "featured": True},
        {"title": "Siebkens Live Music: Northsoul (IndyCar Wknd)", "date": "2026-06-19", "start_time": "7:00 PM", "end_time": "10:00 PM", "link": "https://www.siebkens.com/event/indycar-wknd-live-music-northsoul/"},
        {"title": "Siebkens Live Music: The Donna Woodall Group (IndyCar Wknd)", "date": "2026-06-20", "start_time": "7:00 PM", "end_time": "10:00 PM", "link": "https://www.siebkens.com/event/indycar-wknd-live-music-donna-woodall/"},
        {"title": "Siebkens Summer Concert: Ryan Scheidemeyer & Friends", "date": "2026-06-24", "start_time": "7:00 PM", "end_time": "10:00 PM", "link": "https://www.siebkens.com/event/siebkens-summer-concert-series-ryan-scheidemeyer-friends/"},
        {"title": "Siebkens Summer Concert: The Chili Dogs", "date": "2026-07-01", "start_time": "7:00 PM", "end_time": "10:00 PM", "link": "https://www.siebkens.com/event/siebkens-summer-concert-series-the-chili-dogs-2/"},
        {"title": "Siebkens Summer Concert: Trapper Schoepp", "date": "2026-07-08", "start_time": "7:00 PM", "end_time": "10:00 PM", "link": "https://www.siebkens.com/event/siebkens-summer-concert-series-trapper-schoepp/"},
        {"title": "Siebkens Summer Concert: Erin Krebs & Paul Sucherman", "date": "2026-07-15", "start_time": "7:00 PM", "end_time": "10:00 PM", "link": "https://www.siebkens.com/event/siebkens-summer-concert-series-erin-krebs-and-paul-sucherman/"},
        {"title": "Siebkens Live Music: Livin The Dream (Vintage Wknd)", "date": "2026-07-17", "start_time": "7:00 PM", "end_time": "11:00 PM", "link": "https://www.siebkens.com/event/vintage-wknd-live-music-livin-the-dream/", "featured": True},
        {"title": "Siebkens Summer Concert: Katalysst", "date": "2026-07-22", "start_time": "7:00 PM", "end_time": "10:00 PM", "link": "https://www.siebkens.com/event/siebkens-summer-concert-series-katalysst-2/"},
        {"title": "Siebkens Summer Concert: Valley Fox", "date": "2026-07-29", "start_time": "7:00 PM", "end_time": "10:00 PM", "link": "https://www.siebkens.com/event/siebkens-summer-concert-series-valley-fox-2/"},
        {"title": "Siebkens Live Music: The Chocolateers (IMSA Wknd)", "date": "2026-07-30", "start_time": "7:00 PM", "end_time": "10:00 PM", "link": "https://www.siebkens.com/event/imsa-wknd-live-music-the-chocolateers/", "featured": True},
        {"title": "Siebkens Live Music: Bowser (IMSA Wknd)", "date": "2026-07-31", "start_time": "7:00 PM", "end_time": "10:00 PM", "link": "https://www.siebkens.com/event/imsa-wknd-live-music-bowser/"},
        {"title": "Siebkens Live Music: Deep Pockets (IMSA Wknd)", "date": "2026-08-01", "start_time": "7:00 PM", "end_time": "10:00 PM", "link": "https://www.siebkens.com/event/imsa-weekend-live-music-deep-pockets-2/"},
        {"title": "Siebkens Summer Concert: Mike Brumm with Trust & Follow", "date": "2026-08-05", "start_time": "7:00 PM", "end_time": "10:00 PM", "link": "https://www.siebkens.com/event/siebkens-summer-concert-series-mike-brumm-with-trust-follow/"},
        {"title": "Siebkens Downtown Night Live Music: Sister Winchester", "date": "2026-08-10", "start_time": "7:00 PM", "end_time": "10:00 PM", "link": "https://www.siebkens.com/event/downtown-night-live-music-sister-winchester-3/"},
        {"title": "Siebkens Summer Concert: Bob & Connor McManus", "date": "2026-08-12", "start_time": "7:00 PM", "end_time": "10:00 PM", "link": "https://www.siebkens.com/event/siebkens-summer-concert-series-bob-connor-mcmanus/"},
        {"title": "Siebkens Summer Concert: Pat McCurdy", "date": "2026-08-19", "start_time": "7:00 PM", "end_time": "10:00 PM", "link": "https://www.siebkens.com/event/siebkens-summer-concert-series-pat-mccurdy-5/"},
        {"title": "Siebkens Summer Concert: Celeste Rose", "date": "2026-08-26", "start_time": "7:00 PM", "end_time": "10:00 PM", "link": "https://www.siebkens.com/event/siebkens-summer-concert-series-celeste-rose-2/"},
        {"title": "GT World Challenge Welcome Party: Burgundy Ties", "date": "2026-08-27", "start_time": "6:00 PM", "end_time": "9:00 PM", "link": "https://www.siebkens.com/event/gt-world-challenge-welcome-party-with-live-music-from-burgundy-ties/"},
        {"title": "Siebkens Live Music: Second Hand Stereo (GT World Challenge)", "date": "2026-08-28", "start_time": "7:00 PM", "end_time": "10:00 PM", "link": "https://www.siebkens.com/event/gt-world-challenge-live-music-second-hand-stereo/"},
        {"title": "Siebkens Live Music: Joseph Huber (GT World Challenge)", "date": "2026-08-29", "start_time": "7:00 PM", "end_time": "10:00 PM", "link": "https://www.siebkens.com/event/gt-world-challenge-live-music-joseph-huber/"},
        {"title": "Siebkens Live Music: Boo! The Band (Elktoberfest)", "date": "2026-09-19", "start_time": "7:00 PM", "link": "https://www.siebkens.com/event/vintage-wknd-live-music-boo-the-band/"},
        {"title": "Siebkens Summer Concert: Brent Bel & The Boys", "date": "2026-09-02", "start_time": "7:00 PM", "end_time": "10:00 PM", "link": "https://www.siebkens.com/event/siebkens-summer-concert-series-brent-bel-the-boys-4/"},
    ]

    for c in CONCERTS:
        if c["date"] >= today:
            event = {
                "title": c["title"],
                "date": c["date"],
                "description": "Live music at Siebkens Resort on the shores of Elkhart Lake. Outdoor bandstand outside the Stop-Inn Tavern. Free, family & dog friendly.",
                "location": "Siebkens Resort, 284 S Lake Street, Elkhart Lake, WI 53020",
                "link": c["link"],
                "source": "Siebkens Resort",
                "source_url": "https://www.siebkens.com/events/",
                "lat": 43.8336, "lng": -87.9717,
                "scraped_at": datetime.now().isoformat()
            }
            if c.get("start_time"): event["start_time"] = c["start_time"]
            if c.get("end_time"): event["end_time"] = c["end_time"]
            if c.get("featured"): event["featured"] = True
            events.append(event)

    print(f"  Loaded {len(events)} Siebkens concert events")
    return events

def scrape_elkhartlake_browser_json():
    """Load events from the browser-scraped elkhartlake-live.json file if it exists."""
    import os
    paths = [
        os.path.expanduser("~/Downloads/elkhartlake-live.json"),
        os.path.join(os.path.dirname(__file__), "elkhartlake-live.json"),
    ]
    for path in paths:
        if os.path.exists(path):
            print(f"Loading browser-scraped elkhartlake.com events from {path}...")
            try:
                with open(path) as f:
                    data = json.load(f)
                events = data.get("events", [])
                # Re-tag with correct source
                for e in events:
                    e["source"] = "Elkhart Lake Tourism"
                    e["source_url"] = "https://www.elkhartlake.com/events/"
                print(f"  Loaded {len(events)} events from browser scrape")
                return events
            except Exception as ex:
                print(f"  Error loading {path}: {ex}")
    print("  No elkhartlake-live.json found, using hardcoded events")
    return []

def scrape_elkhartlake_known():
    print("Loading known elkhartlake.com annual events...")
    events = []
    today = datetime.now().strftime("%Y-%m-%d")

    # Browser-scraped directly from elkhartlake.com on 2026-05-13
    # Includes specific named concerts, exact dates, and times
    KNOWN_EVENTS = [
        {"title": "Live Music in The Elk Room: Featuring Seth James", "date": "2026-05-15", "start_time": "7:00 PM", "end_time": "10:00 PM", "location": "The Elk Room at The Osthoff Resort, Elkhart Lake, WI", "link": "https://www.elkhartlake.com/event/live-music-in-the-elk-room-featuring-seth-james/"},
        {"title": "Live Music in The Elk Room: Featuring Mark Croft", "date": "2026-05-16", "start_time": "7:00 PM", "end_time": "10:00 PM", "location": "The Elk Room at The Osthoff Resort, Elkhart Lake, WI", "link": "https://www.elkhartlake.com/event/live-music-in-the-elk-room-featuring-mark-croft/"},
        {"title": "4 Miles of Fitness", "date": "2026-05-18", "start_time": "6:00 PM", "end_time": "8:00 PM", "location": "Road America, Elkhart Lake, WI", "link": "https://www.elkhartlake.com/event/4-miles-of-fitness/", "description": "Bike, walk, or run Road America\'s legendary 4-mile, 14-turn road course. Fan-favorite fitness event on the scenic 640-acre property."},
        {"title": "4 Miles of Fitness", "date": "2026-05-20", "start_time": "6:00 PM", "end_time": "8:00 PM", "location": "Road America, Elkhart Lake, WI", "link": "https://www.elkhartlake.com/event/4-miles-of-fitness/"},
        {"title": "Elkhart Lake Annual Veterans Memorial Tribute", "date": "2026-05-23", "start_time": "10:00 AM", "location": "Elkhart Lake, WI", "link": "https://www.elkhartlake.com/event/elkhart-lake-annual-veterans-memorial-tribute/"},
        {"title": "4 Miles of Fitness", "date": "2026-05-25", "start_time": "6:00 PM", "end_time": "8:00 PM", "location": "Road America, Elkhart Lake, WI", "link": "https://www.elkhartlake.com/event/4-miles-of-fitness/"},
        {"title": "Siebkens Live Music by Kylar Kuzio", "date": "2026-05-27", "start_time": "7:00 PM", "end_time": "10:00 PM", "location": "Siebkens Resort, 284 S Lake Street, Elkhart Lake, WI", "link": "https://www.elkhartlake.com/event/siebkens-live-music-by-kylar-kuzio/", "description": "Kylar Kuzio kicks off the Siebkens Summer Concert Series. Live music on the bandstand outside the Stop-Inn Tavern. Free, family & dog friendly outdoor concert.", "featured": True},
        {"title": "Siebkens Live Music by Jeremiah Jams", "date": "2026-05-29", "start_time": "7:00 PM", "end_time": "11:00 PM", "location": "Siebkens Resort, 284 S Lake Street, Elkhart Lake, WI", "link": "https://www.elkhartlake.com/event/siebkens-live-music-by-jeremiah-jams/", "description": "Live music on the Siebkens bandstand outside the Stop-Inn Tavern. Free, family & dog friendly outdoor concert."},
        {"title": "The Hard Left Moto Show", "date": "2026-05-30", "start_time": "6:00 PM", "location": "Elkhart Lake, WI", "link": "https://www.elkhartlake.com/event/the-hard-left-moto-show/"},
        {"title": "Siebkens Live Music by Dave Steffen & Friends", "date": "2026-05-30", "start_time": "7:30 PM", "location": "Siebkens Resort, 284 S Lake Street, Elkhart Lake, WI", "link": "https://www.elkhartlake.com/events/"},
        {"title": "4 Miles of Fitness", "date": "2026-06-01", "start_time": "6:00 PM", "end_time": "8:00 PM", "location": "Road America, Elkhart Lake, WI", "link": "https://www.elkhartlake.com/event/4-miles-of-fitness/"},
        {"title": "4 Miles of Fitness", "date": "2026-06-03", "start_time": "6:00 PM", "end_time": "8:00 PM", "location": "Road America, Elkhart Lake, WI", "link": "https://www.elkhartlake.com/event/4-miles-of-fitness/"},
        {"title": "Siebkens Live Music by Wire & Nail", "date": "2026-06-19", "start_time": "7:00 PM", "end_time": "10:00 PM", "location": "Siebkens Resort, 284 S Lake Street, Elkhart Lake, WI", "link": "https://www.elkhartlake.com/event/siebkens-live-music-by-wire-nail-2/", "description": "Milwaukee\'s #1 honky tonk, rock and roll band hits the stage for IndyCar Weekend. Free, family & dog friendly outdoor concert.", "featured": True},
        {"title": "Siebkens Live Music by The Squeezebox", "date": "2026-06-20", "start_time": "7:00 PM", "location": "Siebkens Resort, 284 S Lake Street, Elkhart Lake, WI", "link": "https://www.elkhartlake.com/events/"},
        {"title": "Siebkens Live Music by Mikayla Raines", "date": "2026-06-24", "start_time": "7:00 PM", "location": "Siebkens Resort, 284 S Lake Street, Elkhart Lake, WI", "link": "https://www.elkhartlake.com/events/"},
        {"title": "Siebkens Live Music by 7000apart", "date": "2026-07-01", "start_time": "7:00 PM", "end_time": "10:00 PM", "recurrence": "weekly", "recurrence_day": "Wednesday", "end_date": "2026-08-26", "location": "Siebkens Resort, 284 S Lake Street, Elkhart Lake, WI", "link": "https://www.elkhartlake.com/event/siebkens-live-music-by-7000apart/", "description": "7000apart returns to Siebkens Summer Concert Series on Wednesday nights. Free, family & dog friendly outdoor concert."},
        {"title": "Siebkens Block Party", "date": "2026-07-11", "start_time": "11:00 AM", "location": "Siebkens Resort, 284 S Lake Street, Elkhart Lake, WI", "link": "https://www.elkhartlake.com/event/siebkens-block-party/", "description": "Annual Siebkens Block Party with 3 live bands, lawn games, local vendors, and a tasting by Fifth Ward Brewing Company.", "featured": True},
        {"title": "Road America Concours d\'Elegance", "date": "2026-07-17", "end_date": "2026-07-18", "start_time": "6:00 PM", "end_time": "8:00 PM", "location": "Downtown Elkhart Lake, WI", "link": "https://www.elkhartlake.com/event/weathertech-vintage-weekend-with-brian-redman/", "description": "Spectacular display of vintage racecars and luxury sports cars in downtown Elkhart Lake.", "featured": True},
        {"title": "Siebkens Live Music by Chili Dogs", "date": "2026-07-18", "start_time": "7:00 PM", "location": "Siebkens Resort, 284 S Lake Street, Elkhart Lake, WI", "link": "https://www.elkhartlake.com/events/"},
        {"title": "Downtown Night: A Taste of Elkhart Lake", "date": "2026-08-10", "start_time": "5:00 PM", "end_time": "9:00 PM", "location": "Elkhart Lake, WI", "link": "https://www.elkhartlake.com/event/downtown-night-a-taste-of-elkhart-lake/", "description": "Taste your way through signature dishes from Elkhart Lake Chamber Member restaurants, enjoy live music, and let the kids explore activities.", "featured": True},
        {"title": "Elktoberfest", "date": "2026-09-19", "start_time": "10:00 AM", "location": "Downtown Elkhart Lake, WI", "link": "https://www.elkhartlake.com/event/elktoberfest/", "description": "Bavarian fun with stein hoists, brats, pretzels, polka and live music from Boo! The Band at Siebkens. Annual Elktoberfest Run/Walk, family games.", "featured": True},
        {"title": "Old World Christmas Market", "date": "2026-11-21", "location": "Elkhart Lake, WI", "link": "https://www.elkhartlake.com/event/old-world-christmas-market/"},
        # Recurring events
        {"title": "Farmers & Artisans Market", "date": "2026-05-23", "start_time": "8:00 AM", "end_time": "12:00 PM", "recurrence": "weekly", "recurrence_day": "Saturday", "end_date": "2026-10-03", "location": "Village Square, Elkhart Lake, WI", "link": "https://www.elkhartlake.com/event/farmers-artisans-market-3/", "description": "Saturday morning tradition in the Village Square. Fresh vegetables, flowers, cheeses, local arts and specialty products from ~50 vendors."},
        {"title": "Sunset Cruise at Road America", "date": "2026-05-23", "start_time": "5:30 PM", "end_time": "7:00 PM", "recurrence": "weekly", "recurrence_days": "Wednesday,Saturday", "end_date": "2026-09-26", "location": "Road America, N7390 US-12, Elkhart Lake, WI", "link": "https://www.elkhartlake.com/event/sunset-cruise-at-road-america-2/", "description": "A leisurely 3-lap sunset experience of the iconic 4-mile Road America track in your own vehicle."},
        {"title": "4 Miles of Fitness", "date": "2026-05-18", "start_time": "6:00 PM", "end_time": "8:00 PM", "recurrence": "weekly", "recurrence_days": "Monday,Wednesday,Friday", "end_date": "2026-10-30", "location": "Road America, N7390 US-12, Elkhart Lake, WI", "link": "https://www.elkhartlake.com/event/4-miles-of-fitness/", "description": "Bike, walk, or run Road America\'s legendary 4-mile, 14-turn road course. Fan-favorite fitness event."},
        # Fireman\'s Picnic
        {"title": "Elkhart Lake Fireman\'s Picnic — Friday Night", "date": "2026-07-03", "start_time": "7:30 PM", "location": "Elkhart Lake, WI", "link": "https://www.elkhartlake.com/event/elkhart-lake-firemans-picnic/", "description": "Annual 4th of July celebration with live music, food, drinks, and fireworks at dusk.", "featured": True},
        {"title": "Elkhart Lake Fireman\'s Picnic — Sunday", "date": "2026-07-05", "start_time": "11:30 AM", "location": "Downtown Elkhart Lake, WI", "link": "https://www.elkhartlake.com/event/elkhart-lake-firemans-picnic/", "description": "Fireman\'s Parade at 11:30am in downtown Elkhart Lake followed by live music 1:30-5pm."},
        # Jazz on the Vine at Osthoff
        {"title": "Jazz on the Vine at The Osthoff", "date": "2026-05-01", "end_date": "2026-05-02", "start_time": "7:00 PM", "location": "The Osthoff Resort, 101 Osthoff Ave, Elkhart Lake, WI", "link": "https://www.elkhartlake.com/event/jazz-on-the-vine/", "description": "Spectacular live jazz at The Osthoff Resort. Featuring Damien Escobar, Alex Bugnon, and Marqueal Jordan.", "featured": True},
        {"title": "Jazz on the Vine at The Osthoff", "date": "2026-05-08", "end_date": "2026-05-09", "start_time": "7:00 PM", "location": "The Osthoff Resort, 101 Osthoff Ave, Elkhart Lake, WI", "link": "https://www.elkhartlake.com/event/jazz-on-the-vine/"},
        {"title": "Jazz on the Vine at The Osthoff", "date": "2026-05-15", "end_date": "2026-05-16", "start_time": "7:00 PM", "location": "The Osthoff Resort, 101 Osthoff Ave, Elkhart Lake, WI", "link": "https://www.elkhartlake.com/event/jazz-on-the-vine/"},
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
            if e.get("recurrence_days"): event["recurrence_days"] = e["recurrence_days"]
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
            browser = p.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled"],
            )
            ctx = browser.new_context(
                user_agent=HEADERS["User-Agent"],
                viewport={"width": 1400, "height": 900},
                locale="en-US",
                timezone_id="America/Denver",
            )
            page = ctx.new_page()
            page.set_extra_http_headers({
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
            })

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
                            description = desc_el.get_text(strip=True)[:2000] if desc_el else ""

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
            browser = p.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled"],
            )
            ctx = browser.new_context(
                user_agent=HEADERS["User-Agent"],
                viewport={"width": 1400, "height": 900},
                locale="en-US",
                timezone_id="America/Denver",
            )
            page = ctx.new_page()
            page.set_extra_http_headers({
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
            })
            page.goto("https://www.siebkens.com/events/", wait_until="domcontentloaded", timeout=25000)
            page.wait_for_timeout(4000)
            html = page.content()
            browser.close()

        # Siebkens uses The Events Calendar Pro WordPress plugin. The full
        # event roster is embedded as a JSON-LD list of Event objects.
        # Parsing JSON-LD is much more reliable than trying to walk the DOM.
        import json as _json
        ld_blocks = re.findall(
            r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
            html, re.DOTALL,
        )
        raw_events = []
        for block in ld_blocks:
            try:
                data = _json.loads(block)
            except _json.JSONDecodeError:
                continue
            items = data if isinstance(data, list) else [data]
            for item in items:
                if isinstance(item, dict) and item.get("@type") == "Event":
                    raw_events.append(item)

        for ev in raw_events:
            try:
                title = (ev.get("name") or "").strip()
                # Decode HTML entities like &#038; -> &
                import html as _html
                title = _html.unescape(title)
                if len(title) < 3:
                    continue
                start = ev.get("startDate") or ""
                end = ev.get("endDate") or ""
                if not start:
                    continue
                # Parse "2026-05-27T19:00:00+00:00"
                try:
                    sdt = datetime.fromisoformat(start.replace("Z", "+00:00"))
                except ValueError:
                    continue
                date_str = sdt.strftime("%Y-%m-%d")
                start_time = sdt.strftime("%-I:%M %p")
                end_time = None
                end_date = None
                if end:
                    try:
                        edt = datetime.fromisoformat(end.replace("Z", "+00:00"))
                        end_time = edt.strftime("%-I:%M %p")
                        if edt.date() != sdt.date():
                            end_date = edt.strftime("%Y-%m-%d")
                    except ValueError:
                        pass

                # Description has HTML-entity-encoded HTML tags — strip them
                desc_raw = ev.get("description") or ""
                desc_unescaped = (
                    desc_raw.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
                            .replace("&#039;", "'").replace("\\'", "'").replace('\\"', '"')
                )
                description = re.sub(r"<[^>]+>", "", desc_unescaped).strip()
                description = re.sub(r"\s+", " ", description)[:2000]
                if not description:
                    description = "Live music at Siebkens Resort on the shores of Elkhart Lake."

                # Venue name from nested location
                venue_name = None
                loc = ev.get("location") or {}
                if isinstance(loc, dict):
                    venue_name = loc.get("name")

                link = ev.get("url") or "https://www.siebkens.com/events/"

                event = {
                    "title": title,
                    "date": date_str,
                    "description": description,
                    "location": "Siebkens Resort, 284 S Lake St, Elkhart Lake, WI",
                    "venue_name": venue_name or "Siebkens Resort",
                    "link": link,
                    "source": "Siebkens Resort",
                    "source_url": "https://www.siebkens.com/events/",
                    "lat": 43.8336,
                    "lng": -87.9717,
                    "scraped_at": datetime.now().isoformat(),
                }
                if start_time:
                    event["start_time"] = start_time
                if end_time:
                    event["end_time"] = end_time
                if end_date:
                    event["end_date"] = end_date
                image = ev.get("image")
                if image:
                    event["image_url"] = image

                events.append(event)
            except Exception:
                continue

        print(f"  Found {len(events)} events from Siebkens (JSON-LD)")
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
                description = desc_el.get_text(strip=True)[:2000] if desc_el else ""

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
                description = desc_el.get_text(strip=True)[:2000] if desc_el else ""

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
                        "description": description[:2000],
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
            browser = p.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled"],
            )
            ctx = browser.new_context(
                user_agent=HEADERS["User-Agent"],
                viewport={"width": 1400, "height": 900},
                locale="en-US",
                timezone_id="America/Denver",
            )
            page = ctx.new_page()
            page.set_extra_http_headers({
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
            })
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
                description = desc_el.get_text(strip=True)[:2000] if desc_el else ""

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
def _normalize_title_for_match(title: str) -> str:
    """Strip series/venue prefixes and parenthetical suffixes so we can match
    "Bazooka Joe" (osthoff.com) against "The Osthoff Lake Deck Live Music by
    Bazooka Joe" (elkhartlake.com). Returns the bare act name."""
    if not title:
        return ""
    t = re.sub(r"\s+", " ", title.lower().strip())
    # Drop parenthetical event suffixes like "(IMSA Wknd)", "(Indycar Wknd)"
    t = re.sub(r"\s*\([^)]*\)\s*$", "", t)
    # Drop common series/venue prefixes
    prefixes = [
        r"the osthoff lake deck live music by\s+",
        r"osthoff lake deck live music by\s+",
        r"siebkens summer concert series:?\s*",
        r"siebkens summer concert:?\s*",
        r"siebkens live music by\s+",
        r"siebkens live music:?\s*",
        r"siebkens live music featuring\s+",
        r"live music in the elk room:?\s*featuring\s+",
        r"live music by\s+",
        r"live music featuring\s+",
        r"indycar wknd live music:?\s*",
        r"motoamerica wknd live music:?\s*",
        r"imsa w(ee)?k(end)?\s+live music:?\s*",
        r"vintage wknd live music:?\s*",
        r"gt world challenge live music:?\s*",
        r"downtown night live music:?\s*",
    ]
    for prefix in prefixes:
        new_t = re.sub(r"^" + prefix, "", t)
        if new_t != t:
            t = new_t
            break  # only strip one prefix
    # Strip leading punctuation/quotes
    t = re.sub(r"^[\(\"\'\-\s]+", "", t).strip()
    return t


def _series_label_from_record(rec: dict) -> str:
    """Detect which performance series a record belongs to. Checks title,
    venue, location, and description — important for Osthoff API records
    where the title is just the act name ("Bazooka Joe"), the venue is
    empty, and the series ("Live Music at The Lake Deck") is buried in the
    description prose."""
    text = " ".join([
        str(rec.get("title") or ""),
        str(rec.get("venue_name") or ""),
        str(rec.get("location") or ""),
        str(rec.get("description") or ""),
    ]).lower()
    if "lake deck" in text:
        return "The Osthoff Lake Deck"
    if "elk room" in text:
        return "The Elk Room at Osthoff"
    if "siebkens" in text:
        return "Siebkens Live Music"
    return ""


def _series_label(title: str) -> str:
    """Legacy title-only series detection (kept for backwards compat)."""
    return _series_label_from_record({"title": title})


def _merge_duplicate_events(records: list) -> dict:
    """Given multiple records that all refer to the same event (same date,
    same normalized title, same start_time), produce a single merged record.

    Strategy:
      - Title: prefer the shortest non-empty title (cleanest act name)
      - Description: prefer the longest
      - Venue / location / address: prefer the most specific
      - Image: prefer the first non-empty
      - Categories: union all
      - Source: prefer the highest-priority source (venue-direct > Elkhart Lake Tourism > Google Events)
      - Series: add a `series` field if we detect the act is part of a known
        venue's series (Lake Deck, Siebkens, Elk Room)
    """
    source_priority = {
        # Venue-direct / primary organizer wins attribution over the tourism
        # aggregator (matches build_master_and_views.SOURCE_PRIORITY: a venue's
        # own site is more authoritative for its events than the town feed).
        # Title/description/venue are still chosen on their own merits below,
        # so this only sets the source label + canonical link.
        "The Osthoff Resort": 0,
        "Siebkens Resort": 1,
        "Road America": 2,
        "Elkhart Lake Tourism": 3,
        "Google Events": 9,
        "Eventbrite": 9,
        "AllEvents": 9,
    }

    # Pick a base record: the one with the most-specific source priority that
    # also has a real description, to maximize information preserved.
    base = sorted(
        records,
        key=lambda e: (
            source_priority.get(e.get("source", ""), 99),
            -len(e.get("description") or ""),
        ),
    )[0]

    merged = dict(base)

    # Title: shortest non-empty title that's not just the series name
    candidates = []
    for r in records:
        t = (r.get("title") or "").strip()
        if t and len(t) > 3 and "lake deck" not in t.lower()[:20]:
            candidates.append(t)
    if not candidates:
        candidates = [r.get("title") or "" for r in records if r.get("title")]
    if candidates:
        # Pick the cleanest shortest title — usually that's the act name
        # without the venue/series wrapper.
        candidates.sort(key=lambda t: (len(t), t))
        merged["title"] = candidates[0]

    # Description: longest
    descs = [r.get("description") or "" for r in records]
    descs.sort(key=lambda d: -len(d))
    if descs and descs[0]:
        merged["description"] = descs[0]

    # Image: first non-empty
    for r in records:
        if r.get("image_url"):
            merged["image_url"] = r["image_url"]
            break

    # Venue / address: most specific (longest non-empty)
    for field in ("venue_name", "address", "location"):
        candidates = [r.get(field) for r in records if r.get(field)]
        candidates.sort(key=lambda v: -len(v))
        if candidates:
            merged[field] = candidates[0]

    # Categories: union (preserve order)
    cats: list = []
    for r in records:
        for c in r.get("categories") or []:
            if c not in cats:
                cats.append(c)
    if cats:
        merged["categories"] = cats

    # Link: prefer the one matching the canonical source we picked
    base_source = merged.get("source", "")
    for r in records:
        if r.get("source") == base_source and r.get("link"):
            merged["link"] = r["link"]
            break

    # Series label: check title, venue, and location of any input record.
    for r in records:
        series = _series_label_from_record(r)
        if series:
            merged["series"] = series
            break

    return merged


def deduplicate(events):
    """Merge-aware dedup. Groups by (date, normalized_title, start_time) and
    consolidates duplicate records into one enriched entry."""
    groups: dict = {}
    for e in events:
        date = (e.get("date") or "")[:10]
        norm_title = _normalize_title_for_match(e.get("title", ""))[:50]
        start_time = (e.get("start_time") or "").strip().lower()
        # Some Google Events records have no start_time but the same act
        # might have one elsewhere. Match more loosely if start_time is empty.
        key = (date, norm_title, start_time)
        groups.setdefault(key, []).append(e)

    unique = []
    merged_count = 0
    for key, records in groups.items():
        if len(records) == 1:
            # Still tag single records with their series (helps Osthoff-only
            # records show the Lake Deck badge).
            rec = dict(records[0])
            series = _series_label_from_record(rec)
            if series:
                rec["series"] = series
            unique.append(rec)
        else:
            unique.append(_merge_duplicate_events(records))
            merged_count += len(records) - 1

    if merged_count:
        print(f"  [dedup] merged {merged_count} duplicate records into existing entries")
    return unique


# Source-based geo defaults — if a scraper produced an event without lat/lng,
# fill in the city center coordinates so radius filtering still works.
ELKHART_SOURCE_DEFAULTS = {
    "Elkhart Lake Tourism": (43.8330, -88.0426),
    "Road America": (43.7969, -87.9897),
    "The Osthoff Resort": (43.8347, -88.0398),
    "Siebkens Resort": (43.8324, -88.0386),
    "Village of Elkhart Lake": (43.8330, -88.0426),
}

def _fill_default_geo(events):
    """Backfill missing lat/lng from source name. Returns list of patched events."""
    filled = 0
    for e in events:
        if not e.get("lat") or not e.get("lng"):
            src = e.get("source", "")
            if src in ELKHART_SOURCE_DEFAULTS:
                lat, lng = ELKHART_SOURCE_DEFAULTS[src]
                e["lat"] = lat
                e["lng"] = lng
                e["_geo_source"] = "default"  # mark so we know it's not exact
                filled += 1
    if filled:
        print(f"  Filled lat/lng defaults for {filled} events without geo")
    return events


def save_events(events, filename="public/raw/events-elkhartlake.json"):
    events = _fill_default_geo(events)
    # Drop records with non-ISO dates. These are usually UI chrome
    # ("Login", "Need help?") that fragile HTML scrapers grabbed as events,
    # or records where the date field couldn't be parsed (e.g. "See website").
    import re as _re
    before = len(events)
    events = [e for e in events if _re.match(r"^\d{4}-\d{2}-\d{2}$", str(e.get("date","")))]
    dropped = before - len(events)
    if dropped:
        print(f"  [save_events] dropped {dropped} records with non-ISO dates")
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
def main():
    print("=" * 55)
    print("  Yoocal Elkhart Lake Scraper")
    print("=" * 55)
    print()

    all_events = []
    all_events += scrape_road_america()
    all_events += scrape_siebkens_known()
    # Elkhart Lake 2026 Major Events poster — curated annuals.
    try:
        from elkhart_recurring_locals import scrape_elkhart_recurring_locals
        all_events += scrape_elkhart_recurring_locals()
    except Exception as ex:
        print(f"  [elkhart_recurring_locals] skipped: {ex}")
    # elkhartlake.com via the Tribe REST API (the data source behind the
    # public tourism calendar). This replaces the old HTML scrape +
    # hardcoded events list which produced "See website" date entries.
    try:
        from elkhart_tribe_api_scraper import scrape_elkhartlake_tribe_api, scrape_osthoff_tribe_api
        elk_tribe = scrape_elkhartlake_tribe_api()
        if elk_tribe:
            all_events += elk_tribe
        else:
            print("  [Elkhart/Tribe] returned 0 — falling back to legacy hardcoded list")
        # Osthoff publishes its own calendar (Tribe REST) with Aug+Sept Lake
        # Deck shows that elkhartlake.com hasn't syndicated yet.
        try:
            osth_tribe = scrape_osthoff_tribe_api()
            if osth_tribe:
                all_events += osth_tribe
        except Exception as ex2:
            print(f"  [Osthoff/Tribe] failed: {ex2}")
    except Exception as ex:
        print(f"  [Elkhart/Tribe] failed: {ex} — falling back to hardcoded list")
        elk_tribe = []
    # Legacy paths — only used if Tribe API returned nothing (i.e. the API
    # changed or the site is down).
    if not elk_tribe:
        browser_scraped = scrape_elkhartlake_browser_json()
        if browser_scraped:
            all_events += browser_scraped
        else:
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

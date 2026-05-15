#!/usr/bin/env python3
"""
Yoocal Scraper v2 — Park City Events
Sources:
  1. visitparkcity.com  — tourism events
  2. KPCW.org           — community/nonprofit events
  3. Eventbrite         — ticketed events
  4. RunSignup          — races and fitness events
  5. parkrecord.com     — local newspaper (uses Playwright)

Run: python3 scraper.py
Output: events.json
"""

import requests
import os
from bs4 import BeautifulSoup
import json
import re
from datetime import datetime, timedelta

def normalize_date_str(s):
    """Convert ISO datetime string to YYYY-MM-DD"""
    if not s: return None
    m = re.match(r'(\d{4})-(\d{2})-(\d{2})', str(s))
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else None

def extract_time_from_iso(s):
    """Extract 12-hour time string from ISO datetime.
    VPC API returns local Mountain Time without Z suffix — use as-is.
    Only convert if explicitly UTC (ends with Z or +00:00)."""
    if not s: return ""
    m = re.search(r'T(\d{2}):(\d{2})', str(s))
    if not m: return ""
    h, mn = int(m.group(1)), m.group(2)
    # Only subtract for explicit UTC timestamps
    if str(s).endswith('Z') or '+00:00' in str(s):
        h = (h - 6) % 24  # UTC to MDT
    if h == 0 and mn == "00": return ""  # midnight = no time
    ampm = "AM" if h < 12 else "PM"
    h12 = h % 12 or 12
    return f"{h12}:{mn} {ampm}"

def extract_time_from_string(s):
    """Extract first time from a plain string e.g. 'Saturday May 16, 7:00 PM' -> '7:00 PM'"""
    if not s: return ""
    m = re.search(r'\b(\d{1,2}:\d{2}\s?(?:AM|PM|am|pm))', str(s))
    return m.group(1).strip() if m else ""

def extract_end_time_from_string(s):
    """Extract end time from a range string e.g. '5:00 PM - 8:00 PM' -> '8:00 PM'"""
    if not s: return ""
    # Match patterns like "5pm-8pm", "5:00 PM - 8:00 PM", "5:00-8:00pm"
    m = re.search(r'\d{1,2}(?::\d{2})?\s?(?:am|pm|AM|PM)?\s*[-–to]+\s*(\d{1,2}:\d{2}\s?(?:AM|PM|am|pm)|\d{1,2}\s?(?:AM|PM|am|pm))', str(s))
    if m:
        return m.group(1).strip()
    return ""

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# ─────────────────────────────────────────────
# 1. VISIT PARK CITY — Smart API Scraper
# ─────────────────────────────────────────────
def scrape_visit_park_city():
    print("Scraping visitparkcity.com (Smart API)...")
    events = []

    def normalize_date(s):
        m = re.match(r'(\d{4})-(\d{2})-(\d{2})', s or '')
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else None

    def parse_recurrence(rec_str):
        if not rec_str: return None, []
        s = rec_str.lower()
        days = [d.capitalize() for d in ['monday','tuesday','wednesday','thursday','friday','saturday','sunday'] if d in s]
        if 'daily' in s: return 'daily', []
        if days: return ('weekly' if len(days) == 1 else 'weekly_multiple'), days
        if 'monthly' in s: return 'monthly', days
        return None, []

    today = datetime.now()
    start_str = today.strftime("%Y-%m-%d")
    end_str = (today + timedelta(days=120)).strftime("%Y-%m-%d")
    calendar_url = f"https://www.visitparkcity.com/events/calendar/?bounds=false&view=grid&sort=date&filter_daterange%5Bstart%5D={start_str}&filter_daterange%5Bend%5D={end_str}"

    captured_api_url = [None]
    captured_cookies = [None]

    def handle_request(request):
        if 'plugins_events_events_by_date' in request.url and not captured_api_url[0]:
            captured_api_url[0] = request.url
            captured_cookies[0] = request.headers.get('cookie', '')

    try:
        from playwright.sync_api import sync_playwright
        import urllib.parse

        print("  Step 1: Capturing API session token...")
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.on('request', handle_request)
            page.set_extra_http_headers({"User-Agent": HEADERS["User-Agent"]})
            try:
                page.goto(calendar_url, wait_until="domcontentloaded", timeout=30000)
            except:
                pass
            page.wait_for_timeout(8000)
            browser.close()

        if not captured_api_url[0]:
            print("  Could not capture API URL — falling back to basic scrape")
            raise Exception("No API URL captured")

        parsed = urllib.parse.urlparse(captured_api_url[0])
        params = urllib.parse.parse_qs(parsed.query)
        json_param = params.get('json', [''])[0]
        token = params.get('token', [''])[0]
        api_base = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

        query = json.loads(json_param)
        query['options']['limit'] = 200
        if 'fields' in query.get('options', {}):
            query['options']['fields']['admission'] = 1
            query['options']['fields']['cost'] = 1
            query['options']['fields']['price'] = 1
            query['options']['fields']['free'] = 1
            query['options']['fields']['description'] = 1
            query['options']['fields']['contact'] = 1

        new_json = json.dumps(query, separators=(',', ':'))
        full_url = f"{api_base}?json={urllib.parse.quote(new_json)}&token={token}"

        req_headers = dict(HEADERS)
        req_headers['Referer'] = 'https://www.visitparkcity.com/events/calendar/'
        req_headers['Accept'] = 'application/json, text/plain, */*'
        if captured_cookies[0]:
            req_headers['cookie'] = captured_cookies[0]

        print("  Step 2: Fetching all events from API...")
        r = requests.get(full_url, headers=req_headers, timeout=20)

        if r.status_code != 200:
            raise Exception(f"API returned {r.status_code}")

        docs = r.json().get("docs", {}).get("docs", [])
        total = r.json().get("docs", {}).get("count", 0)
        print(f"  Got {len(docs)} events (total available: {total})")

        today_str = datetime.now().strftime("%Y-%m-%d")
        junk = ['not just a ski town', 'summer hiking', 'treat yourself', 'shopping', 'beauty & wellness']
        seen = set()

        for doc in docs:
            try:
                title = (doc.get("title") or "").strip()
                title = title.replace("&#8211;", "–").replace("&amp;", "&").replace("&#039;", "'")
                if not title or len(title) < 3: continue
                if any(j in title.lower() for j in junk): continue
                key = title.lower()[:40]
                if key in seen: continue
                seen.add(key)

                raw_start = doc.get("startDate") or doc.get("date") or ""
                start_date = normalize_date(raw_start)
                raw_time = extract_time_from_iso(raw_start)
                # Drop midnight and 1:00 AM as false VPC defaults
                start_time = "" if raw_time in ["12:00 AM", "1:00 AM"] else raw_time

                raw_end = doc.get("endDate") or ""
                end_date = normalize_date(raw_end)
                raw_end_time = extract_time_from_iso(raw_end)
                end_time = "" if raw_end_time == "12:00 AM" else raw_end_time

                if start_date and start_date < today_str:
                    start_date = today_str

                recurrence, rec_days = parse_recurrence(doc.get("recurrence", ""))
                location = doc.get("location") or "Park City, UT"
                url_path = doc.get("url") or ""
                link = f"https://www.visitparkcity.com{url_path}" if url_path and not url_path.startswith("http") else (url_path or "https://www.visitparkcity.com/events/")

                admission = str(doc.get("admission") or "").strip()
                price_raw = str(doc.get("price") or doc.get("cost") or "").strip()
                price = admission or price_raw
                free_flag = doc.get("free")

                description = str(doc.get("description") or doc.get("description_raw") or "").strip()[:300]
                description = re.sub(r'<[^>]+>', '', description)
                desc_lower = description.lower()

                if free_flag == True or price.lower() in ["free", "0", "$0"] or "free" in desc_lower or price.lower().startswith("free"):
                    is_free = True
                elif price == "" and free_flag is None:
                    is_free = None
                else:
                    is_free = False
                description = re.sub(r'<[^>]+>', '', description)

                lat = doc.get("latitude") or doc.get("listing", {}).get("latitude") if isinstance(doc.get("listing"), dict) else None
                lng = doc.get("longitude") or doc.get("listing", {}).get("longitude") if isinstance(doc.get("listing"), dict) else None

                event = {
                    "title": title,
                    "date": start_date or "See website",
                    "description": description,
                    "location": location,
                    "link": link,
                    "source": "Visit Park City",
                    "source_url": "https://www.visitparkcity.com/events/",
                    "is_free": is_free,
                    "price": price,
                    "scraped_at": datetime.now().isoformat()
                }
                if start_time: event["start_time"] = start_time
                if end_time: event["end_time"] = end_time
                if lat: event["lat"] = float(lat)
                if lng: event["lng"] = float(lng)
                if end_date: event["end_date"] = end_date
                if recurrence:
                    event["recurrence"] = recurrence
                    event["recurrence_day"] = rec_days[0] if len(rec_days) == 1 else ""
                    event["recurrence_days"] = ",".join(rec_days) if len(rec_days) > 1 else ""

                events.append(event)
            except:
                continue

        print(f"  Found {len(events)} events from Visit Park City")

    except Exception as e:
        print(f"  Smart scrape failed ({e}), using basic scrape...")
        try:
            url = "https://www.visitparkcity.com/events/"
            r = requests.get(url, headers=HEADERS, timeout=15)
            soup = BeautifulSoup(r.text, "html.parser")
            for c in (soup.find_all("div", class_=re.compile(r"event", re.I)) or soup.find_all("article")):
                try:
                    title_el = c.find("h2") or c.find("h3") or c.find("h4")
                    if not title_el: continue
                    title = title_el.get_text(strip=True)
                    if len(title) < 3: continue
                    link_el = c.find("a", href=True)
                    link = link_el["href"] if link_el else url
                    if link.startswith("/"): link = "https://www.visitparkcity.com" + link
                    events.append({"title": title, "date": "See website", "description": "",
                                   "location": "Park City, UT", "link": link,
                                   "source": "Visit Park City", "source_url": url,
                                   "scraped_at": datetime.now().isoformat()})
                except: continue
            print(f"  Fallback found {len(events)} events")
        except Exception as e2:
            print(f"  Fallback also failed: {e2}")

    return events


# ─────────────────────────────────────────────
# 2. KPCW COMMUNITY CALENDAR
# ─────────────────────────────────────────────
def scrape_kpcw():
    print("Scraping KPCW.org community calendar...")
    events = []
    try:
        url = "https://www.kpcw.org/kpcw-community-calendar"
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")

        containers = (
            soup.find_all("article") or
            soup.find_all("div", class_=re.compile(r"event|card|item|post", re.I)) or
            soup.find_all("li", class_=re.compile(r"event|item", re.I))
        )

        skip_titles = {"kpcw", "community calendar", "submit", "donate", "listen", "submit it here", "home", "news", "about"}

        for c in containers:
            try:
                title_el = c.find("h2") or c.find("h3") or c.find("h4") or c.find("a")
                if not title_el: continue
                title = title_el.get_text(strip=True)
                if len(title) < 5: continue
                if any(s in title.lower() for s in skip_titles): continue
                if title.lower() in ['home', 'news', 'about', 'contact', 'events', 'calendar']: continue

                date_el = c.find(class_=re.compile(r"date|time|when", re.I)) or c.find("time")
                raw_date = date_el.get_text(strip=True) if date_el else "See website"
                date = normalize_date_str(raw_date) or raw_date
                start_time = extract_time_from_string(raw_date)

                desc_el = c.find("p")
                description = desc_el.get_text(strip=True)[:300] if desc_el else ""

                link_el = c.find("a", href=True)
                link = link_el["href"] if link_el else url
                if link.startswith("/"): link = "https://www.kpcw.org" + link

                event = {
                    "title": title, "date": date, "description": description,
                    "location": "Park City, UT", "link": link,
                    "source": "KPCW Community Calendar",
                    "source_url": url,
                    "scraped_at": datetime.now().isoformat()
                }
                if start_time: event["start_time"] = start_time
                events.append(event)
            except:
                continue

        print(f"  Found {len(events)} events from KPCW")
    except Exception as e:
        print(f"  Error scraping KPCW: {e}")
    return events


# ─────────────────────────────────────────────
# 3. EVENTBRITE
# ─────────────────────────────────────────────
def scrape_eventbrite():
    print("Scraping Eventbrite...")
    events = []

    def normalize_date(date_str):
        if not date_str: return "See website"
        m = re.match(r'(\d{4})-(\d{2})-(\d{2})', date_str)
        if m: return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
        return "See website"

    urls = [
        "https://www.eventbrite.com/d/ut--park-city/events/",
        "https://www.eventbrite.com/d/ut--84060/events/",
    ]

    for url in urls:
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            soup = BeautifulSoup(r.text, "html.parser")

            scripts = soup.find_all("script", type="application/ld+json")
            for script in scripts:
                try:
                    data = json.loads(script.string)
                    items = data if isinstance(data, list) else [data]
                    for item in items:
                        if item.get("@type") not in ["Event", "SocialEvent", "MusicEvent", "BusinessEvent"]:
                            continue
                        title = item.get("name", "")
                        if not title or len(title) < 3: continue

                        raw_start = item.get("startDate", "")
                        date = normalize_date(raw_start)
                        start_time = extract_time_from_iso(raw_start) or extract_time_from_string(raw_start)
                        description = re.sub(r'<[^>]+>', '', item.get("description", ""))[:300]

                        loc = item.get("location", {})
                        if isinstance(loc, dict):
                            addr = loc.get("address", {})
                            city = addr.get("addressLocality", "") if isinstance(addr, dict) else ""
                            state = addr.get("addressRegion", "") if isinstance(addr, dict) else ""
                            venue = loc.get("name", "")
                            location = f"{venue} {city} {state}".strip()
                        else:
                            location = "Park City, UT"

                        if location and 'ut' not in location.lower() and 'utah' not in location.lower() and 'park city' not in location.lower():
                            continue

                        link = item.get("url", url)
                        offers = item.get("offers", {})
                        price = offers.get("price", "") if isinstance(offers, dict) else ""

                        event = {
                            "title": title,
                            "date": date,
                            "description": description,
                            "location": location or "Park City, UT",
                            "link": link,
                            "price": str(price),
                            "source": "Eventbrite",
                            "source_url": url,
                            "scraped_at": datetime.now().isoformat()
                        }
                        if start_time: event["start_time"] = start_time
                        events.append(event)
                except:
                    continue

            for card in soup.find_all("div", attrs={"data-event-id": True}):
                try:
                    title_el = card.find(["h2","h3","h4"]) or card.find(class_=re.compile(r"title", re.I))
                    if not title_el: continue
                    title = title_el.get_text(strip=True)
                    if len(title) < 3: continue
                    date_el = card.find("time") or card.find(class_=re.compile(r"date", re.I))
                    raw_date = date_el.get("datetime", "") if date_el else ""
                    date = normalize_date(raw_date)
                    start_time = extract_time_from_iso(raw_date)
                    link_el = card.find("a", href=True)
                    link = link_el["href"] if link_el else url
                    event = {
                        "title": title, "date": date, "description": "",
                        "location": "Park City, UT", "link": link,
                        "source": "Eventbrite", "source_url": url,
                        "scraped_at": datetime.now().isoformat()
                    }
                    if start_time: event["start_time"] = start_time
                    events.append(event)
                except:
                    continue

        except Exception as e:
            print(f"  Eventbrite URL failed ({url}): {e}")
            continue

    print(f"  Found {len(events)} events from Eventbrite")
    return events


# ─────────────────────────────────────────────
# 4. RUNNING IN THE USA
# ─────────────────────────────────────────────
def scrape_running_in_the_usa():
    print("Scraping runningintheusa.com for Park City races...")
    events = []
    try:
        url = "https://www.runningintheusa.com/race/list/park%20city-ut/upcoming"
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")

        containers = (
            soup.find_all("div", class_=re.compile(r"race|event|result|card|row|item", re.I)) or
            soup.find_all("tr") or
            soup.find_all("li")
        )

        for c in containers:
            try:
                title_el = c.find("a") or c.find("h2") or c.find("h3") or c.find("h4")
                if not title_el: continue
                title = title_el.get_text(strip=True)
                skip = ["more information", "details", "update", "save", "upcoming races", "sort by"]
                if len(title) < 3 or title.lower() in skip: continue

                date_el = c.find(class_=re.compile(r"date|time", re.I)) or c.find("time")
                raw_date = date_el.get_text(strip=True) if date_el else "See website"
                date = normalize_date_str(raw_date) or raw_date
                start_time = extract_time_from_string(raw_date)

                dist_el = c.find(class_=re.compile(r"dist|distance|type", re.I))
                distance = dist_el.get_text(strip=True) if dist_el else ""

                link_el = c.find("a", href=True)
                link = link_el["href"] if link_el else url
                if link.startswith("/"): link = "https://www.runningintheusa.com" + link

                event = {
                    "title": title,
                    "date": date,
                    "description": f"Race in Park City, UT. {distance}".strip().rstrip("."),
                    "location": "Park City, UT",
                    "link": link,
                    "source": "Running in the USA",
                    "source_url": url,
                    "category": "sports",
                    "scraped_at": datetime.now().isoformat()
                }
                if start_time: event["start_time"] = start_time
                events.append(event)
            except:
                continue

    except Exception as e:
        print(f"  HTTP scrape failed ({e}), using known races only")

    known_races = [
        {
            "title": "Running with Ed 2026",
            "date": "2026-05-16",
            "start_time": "7:00 AM",
            "description": "Park City's favorite community relay race fundraiser for the Park City Education Foundation. 27.6 mile 8-leg relay starting at Basin Recreation Fieldhouse.",
            "location": "Basin Recreation Fieldhouse, Park City, UT",
            "link": "https://www.runningwithed.com",
            "source": "Running in the USA",
            "source_url": "https://www.runningintheusa.com",
            "category": "sports",
            "scraped_at": datetime.now().isoformat()
        },
        {
            "title": "Park City Trail Series — 5K",
            "date": "2026-06-06",
            "start_time": "7:00 AM",
            "description": "Race 1 of 3 in the Park City Trail Series. A forgiving 5K course on Park City's iconic trails, perfect for new and seasoned trail runners alike. Finisher's medal and race swag included.",
            "location": "Park City, UT",
            "link": "https://runsignup.com/Race/UT/ParkCity/ParkCityTrailSeriesFullSeries",
            "source": "Running in the USA",
            "source_url": "https://www.runningintheusa.com",
            "category": "sports",
            "featured": True,
            "scraped_at": datetime.now().isoformat()
        },
        {
            "title": "Park City Trail Series — 10K",
            "date": "2026-07-11",
            "start_time": "7:00 AM",
            "description": "Race 2 of 3 in the Park City Trail Series. A 10K on Park City's iconic trails. Mix and match races or sign up for the full series.",
            "location": "Park City, UT",
            "link": "https://runsignup.com/Race/UT/ParkCity/ParkCityTrailSeriesFullSeries",
            "source": "Running in the USA",
            "source_url": "https://www.runningintheusa.com",
            "category": "sports",
            "featured": True,
            "scraped_at": datetime.now().isoformat()
        },
        {
            "title": "Park City Trail Series — Half Marathon",
            "date": "2026-08-01",
            "start_time": "7:00 AM",
            "description": "Race 3 of 3 in the Park City Trail Series. A half marathon on Park City's iconic trails to cap the summer series. Finisher's medal and race swag included.",
            "location": "Park City, UT",
            "link": "https://runsignup.com/Race/UT/ParkCity/ParkCityTrailSeriesFullSeries",
            "source": "Running in the USA",
            "source_url": "https://www.runningintheusa.com",
            "category": "sports",
            "featured": True,
            "scraped_at": datetime.now().isoformat()
        },
        {
            "title": "Triple Trail Challenge — Round Valley Rambler & Jupiter Peak",
            "date": "2026-06-13",
            "start_time": "7:00 AM",
            "description": "Three-race series: Round Valley Rambler Half Marathon, Jupiter Peak 25K, and Mid Mountain 50K. June through August.",
            "location": "Park City, UT",
            "link": "https://www.runttc.com",
            "source": "Running in the USA",
            "source_url": "https://www.runningintheusa.com",
            "category": "sports",
            "scraped_at": datetime.now().isoformat()
        }
    ]

    existing_titles = {e["title"].lower() for e in events}
    for race in known_races:
        if race["title"].lower() not in existing_titles:
            events.append(race)

    print(f"  Found {len(events)} races from Running in the USA")
    return events


# ─────────────────────────────────────────────
# 5. PARK RECORD — AI-powered + hardcoded fallback
# ─────────────────────────────────────────────
def scrape_park_record():
    print("Scraping Park Record (AI-powered)...")
    events = []

    KNOWN_PARK_RECORD_EVENTS = [
        {
            "title": "Something Rotten Jr. — Egyptian Theatre YouTheatre",
            "date": "2026-05-09",
            "end_date": "2026-05-10",
            "start_time": "1:00 PM",
            "description": "YouTheatre presents 'Something Rotten Jr.' at 1pm & 5pm at Randy Barton Black Box Theatre, 330 Main St. Tickets $10 adults, free ages 17 & under.",
            "location": "Egyptian Theatre, 330 Main St, Park City",
            "link": "https://www.parkcityshows.com",
            "source": "The Park Record",
            "source_url": "https://www.parkrecord.com/2026/05/08/scene-happenings-may-9-to-may-12/",
            "scraped_at": datetime.now().isoformat()
        },
        {
            "title": "Sunday Craft at Swaner EcoCenter",
            "date": "2026-05-11",
            "end_date": "2026-10-31",
            "start_time": "11:00 AM",
            "recurrence": "weekly",
            "recurrence_day": "Sunday",
            "description": "Sunday Craft every Sunday 11am-1pm at Swaner Preserve & EcoCenter, 1258 Center Drive. Upcycled nature-themed craft. Free.",
            "location": "Swaner Preserve & EcoCenter, 1258 Center Drive, Kimball Junction",
            "link": "https://www.swanerecocenter.org",
            "source": "The Park Record",
            "source_url": "https://www.parkrecord.com/2026/05/08/scene-happenings-may-9-to-may-12/",
            "scraped_at": datetime.now().isoformat()
        },
        {
            "title": "Local Speaker Series: Improvisation with AishaZCello",
            "date": "2026-05-12",
            "start_time": "5:00 PM",
            "description": "Free presentation at Park City Library, 5pm Tuesday. Cellist Aisha Z discusses and performs her live looping cello project.",
            "location": "Park City Library, 1255 Park Ave",
            "link": "https://www.parkcitylibrary.org",
            "source": "The Park Record",
            "source_url": "https://www.parkrecord.com/2026/05/08/scene-happenings-may-9-to-may-12/",
            "scraped_at": datetime.now().isoformat()
        },
        {
            "title": "Summit County Library Chess Club",
            "date": "2026-05-11",
            "end_date": "2026-12-31",
            "start_time": "6:00 PM",
            "recurrence": "weekly",
            "recurrence_day": "Monday",
            "description": "Chess Club meets 6-7:45pm on 2nd and 4th Mondays at Kimball Junction Branch, 1885 W. Ute Blvd, Room 133. All abilities welcome, ages 18+.",
            "location": "Kimball Junction Library, 1885 W. Ute Blvd",
            "link": "https://summit.events.mylibrary.digital",
            "source": "The Park Record",
            "source_url": "https://www.parkrecord.com/2026/05/08/scene-happenings-may-9-to-may-12/",
            "scraped_at": datetime.now().isoformat()
        },
    ]

    try:
        from playwright.sync_api import sync_playwright
        print("  Loading Park Record calendar with Playwright...")

        def extract_events_from_page(page):
            return page.evaluate("""() => {
                const events = [];
                const allEventEls = document.querySelectorAll('.eventInfo');
                allEventEls.forEach(el => {
                    let parent = el.parentElement;
                    let date = '';
                    for (let i = 0; i < 8; i++) {
                        if (!parent) break;
                        const dateEl = parent.querySelector('[class*="csDate"]');
                        if (dateEl && !el.contains(dateEl)) { date = dateEl.innerText?.trim(); break; }
                        parent = parent.parentElement;
                    }
                    const title = el.querySelector('.csOneLine span')?.innerText?.trim();
                    const venue = el.querySelector('.csVenue span')?.innerText?.trim();
                    const time = el.querySelector('.csTime')?.innerText?.trim();
                    const link = el.closest('a')?.href || el.querySelector('a')?.href || '';
                    if (title) events.push({title, venue, time, date, link});
                });
                return events;
            }""")

        all_extracted = []
        seen_keys = set()

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)

            for day_offset in range(30):
                target_date = datetime.now() + timedelta(days=day_offset)
                date_str = target_date.strftime("%Y-%m-%d")
                url = f"https://www.parkrecord.com/calendar/#!/show?start={date_str}"

                page = browser.new_page()
                page.set_extra_http_headers({"User-Agent": HEADERS["User-Agent"]})
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=20000)
                    page.wait_for_timeout(6000)
                    try:
                        page.wait_for_selector('.eventInfo', timeout=8000)
                        page.wait_for_timeout(2000)
                    except:
                        pass

                    extracted = extract_events_from_page(page)
                    day_count = 0
                    for item in extracted:
                        title = item.get("title","").lower()[:40]
                        key = f"{title}|{date_str}"
                        if title and key not in seen_keys:
                            seen_keys.add(key)
                            item["_scrape_date"] = date_str
                            all_extracted.append(item)
                            day_count += 1
                    print(f"    {date_str}: {len(extracted)} visible, {day_count} new")
                except Exception as e:
                    pass
                finally:
                    page.close()

            browser.close()

        print(f"  DOM scraper found {len(all_extracted)} unique events across 30 days")
        print(f"  Fetching event details (price, description)...")

        detail_cache = {}
        unique_links = list({item.get("link","") for item in all_extracted if item.get("link","")})[:100]

        def fetch_event_detail(link):
            if not link or link in detail_cache: return
            try:
                r = requests.get(link, headers=HEADERS, timeout=8)
                soup = BeautifulSoup(r.text, "html.parser")
                detail = {}
                price_el = soup.find(string=re.compile(r'Price|Cost|Admission', re.I))
                if price_el:
                    parent = price_el.parent
                    next_el = parent.find_next_sibling() or parent.parent.find_next_sibling()
                    if next_el:
                        price_text = next_el.get_text(strip=True)
                        if price_text:
                            detail['price'] = price_text
                            detail['is_free'] = 'free' in price_text.lower() or price_text in ['0', '$0']
                desc_el = soup.find(string=re.compile(r'Description', re.I))
                if desc_el:
                    parent = desc_el.parent
                    next_el = parent.find_next_sibling()
                    if next_el:
                        detail['description'] = next_el.get_text(strip=True)[:300]
                detail_cache[link] = detail
            except:
                detail_cache[link] = {}

        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=10) as executor:
            executor.map(fetch_event_detail, unique_links)

        today_str = datetime.now().strftime("%Y-%m-%d")
        for item in all_extracted:
            title = item.get("title", "").strip()
            if not title or len(title) < 3: continue

            link = item.get("link", "")
            m = re.search(r'(\d{4}-\d{2}-\d{2})T', link)
            date = m.group(1) if m else item.get("_scrape_date")

            venue = item.get("venue", "") or "Park City, UT"
            time_str = item.get("time", "")
            # Normalize time from Park Record (e.g. "7:00pm" -> "7:00 PM")
            start_time = ""
            end_time = ""
            if time_str:
                t = re.search(r'(\d{1,2}:\d{2})\s?(am|pm|AM|PM)', time_str)
                if t:
                    start_time = f"{t.group(1)} {t.group(2).upper()}"
                else:
                    start_time = time_str
                end_time = extract_end_time_from_string(time_str)
            # Always try link URL as fallback if no time found yet
            if not start_time:
                t = re.search(r'\d{4}-\d{2}-\d{2}T(\d{2})', link)
                if t:
                    h = int(t.group(1))
                    if h != 0:
                        ampm = "AM" if h < 12 else "PM"
                        h12 = h % 12 or 12
                        start_time = f"{h12}:00 {ampm}"

            detail = detail_cache.get(link, {})
            description = detail.get('description', '')
            if not description:
                description = f"At {venue}." if venue and venue != "Park City, UT" else ""
                if time_str:
                    description = f"{time_str} at {venue}." if venue else time_str

            # Try extracting end time from description if not found yet
            if not end_time and description:
                end_time = extract_end_time_from_string(description)

            price = detail.get('price', '')
            is_free = detail.get('is_free', None)

            # Better free/paid from description text since detail fetch is often blocked
            if is_free is None and description:
                desc_lower = description.lower()
                if any(w in desc_lower for w in ['free admission', 'free event', 'no cost', 'no charge', 'free and open', 'free to attend', 'free entry', 'at no cost']):
                    is_free = True
                elif any(w in desc_lower for w in ['tickets', 'admission', '$', 'purchase', 'register', 'registration required', 'fee']):
                    is_free = False

            event = {
                "title": title,
                "date": date or "See website",
                "description": description,
                "location": venue or "Park City, UT",
                "link": link or "https://www.parkrecord.com/calendar/",
                "source": "The Park Record",
                "source_url": "https://www.parkrecord.com/calendar/",
                "price": price,
                "is_free": is_free,
                "scraped_at": datetime.now().isoformat()
            }
            if start_time: event["start_time"] = start_time
            if end_time: event["end_time"] = end_time
            events.append(event)

        if events:
            print(f"  Found {len(events)} events from Park Record calendar")
            existing = {e["title"].lower()[:30] for e in events}
            for e in KNOWN_PARK_RECORD_EVENTS:
                if e["title"].lower()[:30] not in existing:
                    events.append(e)
            print(f"  Total Park Record events: {len(events)}")
            return events

    except Exception as e:
        print(f"  Playwright DOM scrape failed: {e}")

    try:
        article_url = ""
        today_dt = datetime.now()

        for days_back in range(0, 14):
            check_date = datetime(today_dt.year, today_dt.month, max(1, today_dt.day - days_back))
            url = f"https://www.parkrecord.com/{check_date.year}/{str(check_date.month).zfill(2)}/"
            try:
                r = requests.get(url, headers=HEADERS, timeout=10)
                soup = BeautifulSoup(r.text, "html.parser")
                for a in soup.find_all("a", href=True):
                    href = a["href"]
                    if "scene-happenings" in href or "community-calendar" in href:
                        article_url = href
                        break
                if article_url:
                    break
            except:
                continue

        if not article_url:
            try:
                search_url = "https://www.parkrecord.com/?s=scene+happenings"
                r = requests.get(search_url, headers=HEADERS, timeout=10)
                soup = BeautifulSoup(r.text, "html.parser")
                for a in soup.find_all("a", href=True):
                    href = a["href"]
                    if "scene-happenings" in href and "2026" in href:
                        article_url = href
                        break
            except:
                pass

        if not article_url:
            article_url = "https://www.parkrecord.com/2026/05/08/scene-happenings-may-9-to-may-12/"

        print(f"  Fetching: {article_url}")

        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.set_extra_http_headers({"User-Agent": HEADERS["User-Agent"]})
                page.goto(article_url, wait_until="domcontentloaded", timeout=20000)
                page.wait_for_timeout(2000)
                html = page.content()
                browser.close()
            soup = BeautifulSoup(html, "html.parser")
        except:
            r = requests.get(article_url, headers=HEADERS, timeout=15)
            soup = BeautifulSoup(r.text, "html.parser")

        article_body = (
            soup.find("div", class_=re.compile(r"article-body|entry-content|post-content|content", re.I)) or
            soup.find("article") or soup.find("main")
        )
        article_text = article_body.get_text(separator="\n", strip=True)[:8000] if article_body else ""

        if article_text and len(article_text) > 200 and "checking your browser" not in article_text.lower():
            print(f"  Article text: {len(article_text)} chars — Using AI to extract events...")
            api_key = os.environ.get("ANTHROPIC_API_KEY", "")
            if api_key:
                prompt = f"""Read this Park City newspaper article and extract all events as a JSON array.
Each item: title, date (e.g. "May 12" or "every Sunday"), time (e.g. "7:00 PM" or ""), location (or "Park City, UT"), description (1-2 sentences), link (URL if mentioned or ""), is_free (true/false/null).
Only real events. Return ONLY valid JSON array, no other text.

ARTICLE:
{article_text}"""
                response = requests.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={"Content-Type": "application/json", "x-api-key": api_key, "anthropic-version": "2023-06-01"},
                    json={"model": "claude-sonnet-4-5", "max_tokens": 4000, "messages": [{"role": "user", "content": prompt}]},
                    timeout=30
                )
                if response.status_code == 200:
                    content = response.json().get("content", [{}])[0].get("text", "").strip()
                    content = re.sub(r'```(?:json)?', '', content).strip().rstrip('`').strip()
                    match = re.search(r'\[.*\]', content, re.DOTALL)
                    if match:
                        extracted = json.loads(match.group(0))
                        for item in extracted:
                            if not item.get("title"): continue
                            date_str = item.get("date", "See website")
                            time_str = item.get("time", "")
                            event = {
                                "title": item["title"],
                                "date": date_str,
                                "description": item.get("description", ""),
                                "location": item.get("location", "Park City, UT"),
                                "link": item.get("link", article_url) or article_url,
                                "source": "The Park Record",
                                "source_url": article_url,
                                "scraped_at": datetime.now().isoformat()
                            }
                            if time_str: event["start_time"] = time_str
                            events.append(event)
                        print(f"  AI extracted {len(events)} events from Park Record")
                else:
                    print(f"  Claude API error: {response.status_code}")
        else:
            print("  Cloudflare blocked — using hardcoded Park Record events")

    except Exception as e:
        print(f"  Park Record AI error: {e}")

    existing = {e["title"].lower()[:30] for e in events}
    for e in KNOWN_PARK_RECORD_EVENTS:
        if e["title"].lower()[:30] not in existing:
            events.append(e)

    print(f"  Found {len(events)} total events from Park Record")
    return events


# ─────────────────────────────────────────────
# HANDLE RECURRING EVENTS
# ─────────────────────────────────────────────
def handle_recurring(events):
    today = datetime.now().strftime("%Y-%m-%d")
    end_of_year = "2026-12-31"

    RECURRING = {
        "fascia rolling class": {
            "recurrence": "weekly", "day": "Monday",
            "start": today, "end": "2026-10-31",
            "description": "Weekly fascia rolling wellness class every Monday at Rise Dental Wellness."
        },
        "group fitness classes": {
            "recurrence": "daily",
            "start": today, "end": end_of_year,
            "description": "Daily group fitness classes at Park City Municipal Athletic & Recreation Center."
        },
        "plunj park city": {
            "recurrence": "daily",
            "start": today, "end": end_of_year,
            "description": "Cold plunge and wellness experience open daily at PLUNJ Park City."
        },
        "progressive art experience": {
            "recurrence": "daily",
            "start": today, "end": end_of_year,
            "description": "Ongoing rotating art experience at Park City Fine Art on Main Street."
        },
        "last friday gallery stroll": {
            "recurrence": "monthly_last_friday",
            "start": today, "end": end_of_year,
            "description": "Monthly gallery stroll on the last Friday of each month on Main Street."
        },
        "park silly sunday market": {
            "recurrence": "weekly", "day": "Sunday",
            "start": "2026-06-14", "end": "2026-09-27",
            "description": "Weekly outdoor market every Sunday. Local vendors, food, and live music."
        },
        "deer creek express": {
            "recurrence": "weekly_multiple", "days": ["Monday","Thursday","Friday","Saturday"],
            "start": "2026-05-11", "end": "2026-10-31",
            "description": "Scenic train ride through Heber Valley. Runs Monday, Thursday, Friday & Saturday through October."
        },
        "website is live selling gift boxes": {
            "recurrence": "daily",
            "start": today, "end": end_of_year,
            "description": "Local artisan gift boxes available online and in-store at Maker Union."
        },
    }

    for event in events:
        title_key = event["title"].lower().strip()
        for key, info in RECURRING.items():
            if key in title_key:
                event["date"] = info["start"]
                event["end_date"] = info["end"]
                event["recurrence"] = info.get("recurrence", "")
                event["recurrence_day"] = info.get("day", "")
                event["recurrence_days"] = ",".join(info.get("days", []))
                if info.get("description"):
                    event["description"] = info["description"]
                break

    return events


def deduplicate(events):
    # Sort so Park Record comes first — it has times, prefer it over VPC
    source_priority = {"The Park Record": 0, "Google Events": 1, "Running in the USA": 2, "Visit Park City": 3}
    events.sort(key=lambda e: source_priority.get(e.get("source", ""), 99))

    seen = set()
    unique = []
    for e in events:
        title = re.sub(r'\s+', ' ', e["title"].lower().strip())[:40]
        # Strip leading punctuation like quotes/parens
        title_clean = re.sub(r'^[\(\"\'\-\s]+', '', title)[:35]
        # Also try without subtitle (before colon) for broader matching
        title_no_sub = title_clean.split(':')[0].strip()[:30]
        date = e.get("date", "")[:10]
        key_full = f"{title_clean}|{date}"
        key_short = f"{title_no_sub}|{date}"
        if key_full not in seen and key_short not in seen:
            seen.add(key_full)
            seen.add(key_short)
            unique.append(e)
    return unique


# ─────────────────────────────────────────────
# 6. SERPAPI — Google Events for Park City
# ─────────────────────────────────────────────
def scrape_google_events():
    print("Scraping Google Events via SerpApi...")
    events = []
    SERPAPI_KEY = os.environ.get("SERPAPI_KEY", "")

    queries = [
        "events in Park City Utah",
        "concerts Park City Utah",
        "Park City Utah festivals",
        "things to do Park City Utah this weekend",
    ]

    seen = set()

    for query in queries:
        try:
            url = "https://serpapi.com/search"
            params = {
                "engine": "google_events",
                "q": query,
                "location": "Park City, Utah, United States",
                "gl": "us",
                "hl": "en",
                "api_key": SERPAPI_KEY
            }
            r = requests.get(url, params=params, timeout=15)
            if r.status_code != 200:
                print(f"  SerpApi error {r.status_code} for '{query}'")
                continue

            data = r.json()
            results = data.get("events_results", [])
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
                    date = normalize_date_str(start_date) or normalize_date_str(when) or "See website"
                    start_time = extract_time_from_string(when)

                    address = item.get("address", [])
                    if isinstance(address, list):
                        location = ", ".join(address)
                    else:
                        location = str(address) or "Park City, UT"

                    if location and not any(x in location.lower() for x in ['park city', 'ut', 'utah', 'heber', 'summit']):
                        continue

                    link = item.get("link", "") or item.get("event_location_map", {}).get("link", "")
                    ticket_info = item.get("ticket_info", [])
                    if ticket_info and isinstance(ticket_info, list):
                        link = ticket_info[0].get("link", link)

                    is_free = None
                    description = item.get("description", "")
                    if "free" in description.lower() or "free" in title.lower():
                        is_free = True
                    elif ticket_info:
                        is_free = False

                    thumbnail = item.get("thumbnail", "")

                    event = {
                        "title": title,
                        "date": date,
                        "description": description[:300],
                        "location": location or "Park City, UT",
                        "link": link or "https://www.google.com/search?q=" + title.replace(" ", "+"),
                        "source": "Google Events",
                        "source_url": "https://www.google.com",
                        "is_free": is_free,
                        "thumbnail": thumbnail,
                        "scraped_at": datetime.now().isoformat()
                    }
                    if start_time: event["start_time"] = start_time
                    events.append(event)
                except:
                    continue

        except Exception as e:
            print(f"  SerpApi error for '{query}': {e}")
            continue

    print(f"  Found {len(events)} unique events from Google Events")
    return events


def scrape_utah_com():
    print("Scraping utah.com Park City events...")
    events = []
    try:
        urls = [
            "https://www.utah.com/events/?location=Park+City&radius=10",
            "https://www.utah.com/events/park-city/",
        ]
        for url in urls:
            try:
                r = requests.get(url, headers=HEADERS, timeout=15)
                soup = BeautifulSoup(r.text, "html.parser")
                containers = (
                    soup.find_all("article") or
                    soup.find_all("div", class_=re.compile(r"event|card|listing", re.I)) or
                    soup.find_all("li", class_=re.compile(r"event|item", re.I))
                )
                for c in containers:
                    try:
                        title_el = c.find("h2") or c.find("h3") or c.find("h4")
                        if not title_el: continue
                        title = title_el.get_text(strip=True)
                        if len(title) < 3: continue
                        date_el = c.find(class_=re.compile(r"date|time|when", re.I)) or c.find("time")
                        raw_date = date_el.get_text(strip=True) if date_el else ""
                        date = normalize_date_str(raw_date) or "See website"
                        start_time = extract_time_from_string(raw_date)
                        desc_el = c.find("p")
                        description = desc_el.get_text(strip=True)[:300] if desc_el else ""
                        link_el = c.find("a", href=True)
                        link = link_el["href"] if link_el else url
                        if link.startswith("/"): link = "https://www.utah.com" + link
                        event = {
                            "title": title, "date": date, "description": description,
                            "location": "Park City, UT", "link": link,
                            "source": "Utah.com", "source_url": url,
                            "scraped_at": datetime.now().isoformat()
                        }
                        if start_time: event["start_time"] = start_time
                        events.append(event)
                    except: continue
                if events: break
            except Exception as e:
                print(f"  utah.com URL failed: {e}")
                continue
        print(f"  Found {len(events)} events from utah.com")
    except Exception as e:
        print(f"  Error scraping utah.com: {e}")
    return events


# ─────────────────────────────────────────────
# 7. PARK CITY ARTS COUNCIL (pcscarts.org)
# ─────────────────────────────────────────────
def scrape_arts_council():
    print("Scraping Park City Arts Council events...")
    events = []
    try:
        from playwright.sync_api import sync_playwright
        url = "https://www.pcscarts.org/event-calendar"
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.set_extra_http_headers({"User-Agent": HEADERS["User-Agent"]})
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
            except:
                pass
            page.wait_for_timeout(5000)
            html = page.content()
            browser.close()

        soup = BeautifulSoup(html, "html.parser")
        containers = (
            soup.find_all("article") or
            soup.find_all("div", class_=re.compile(r"event|tribe|card", re.I)) or
            soup.find_all("li", class_=re.compile(r"event|tribe", re.I))
        )
        for c in containers:
            try:
                title_el = c.find("h2") or c.find("h3") or c.find("h4") or c.find(class_=re.compile(r"title", re.I))
                if not title_el: continue
                title = title_el.get_text(strip=True)
                if len(title) < 3: continue
                date_el = c.find(class_=re.compile(r"date|time|start", re.I)) or c.find("time") or c.find("abbr")
                raw_date = date_el.get_text(strip=True) if date_el else ""
                date = normalize_date_str(raw_date) or "See website"
                start_time = extract_time_from_string(raw_date)
                desc_el = c.find("p")
                description = desc_el.get_text(strip=True)[:300] if desc_el else ""
                link_el = c.find("a", href=True)
                link = link_el["href"] if link_el else url
                if link.startswith("/"): link = "https://www.pcscarts.org" + link
                event = {
                    "title": title, "date": date, "description": description,
                    "location": "Park City, UT", "link": link,
                    "source": "PC Arts Council", "source_url": url,
                    "scraped_at": datetime.now().isoformat()
                }
                if start_time: event["start_time"] = start_time
                events.append(event)
            except: continue
        print(f"  Found {len(events)} events from Arts Council")
    except Exception as e:
        print(f"  Error scraping Arts Council: {e}")
    return events


def save_events(events, filename="public/events.json"):
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
    print("  Yoocal Scraper v2 -- Park City Events")
    print("=" * 55)
    print()

    all_events = []
    all_events += scrape_visit_park_city()
    all_events += scrape_kpcw()
    all_events += scrape_eventbrite()
    all_events += scrape_running_in_the_usa()
    all_events += scrape_park_record()
    all_events += scrape_google_events()
    all_events += scrape_utah_com()
    all_events += scrape_arts_council()

    print(f"\nTotal raw events: {len(all_events)}")
    unique = deduplicate(all_events)
    print(f"After deduplication: {len(unique)}")
    unique = handle_recurring(unique)
    print(f"After recurring tagging: {len(unique)}")

    save_events(unique)

    print()
    print("Done! Sample events found:")
    for e in unique[:10]:
        print(f"  [{e['source']}] {e['title']} -- {e['date']} {e.get('start_time','')}")

if __name__ == "__main__":
    main()

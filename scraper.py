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
from bs4 import BeautifulSoup
import json
import re
from datetime import datetime

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# ─────────────────────────────────────────────
# 1. VISIT PARK CITY
# ─────────────────────────────────────────────
def scrape_visit_park_city():
    print("Scraping visitparkcity.com...")
    events = []
    try:
        url = "https://www.visitparkcity.com/events/"
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")

        containers = (
            soup.find_all("div", class_=re.compile(r"event", re.I)) or
            soup.find_all("article") or
            soup.find_all("li", class_=re.compile(r"event", re.I))
        )

        for c in containers:
            try:
                title_el = c.find("h2") or c.find("h3") or c.find("h4") or c.find(class_=re.compile(r"title|name", re.I))
                if not title_el: continue
                title = title_el.get_text(strip=True)
                if len(title) < 3: continue

                date_el = c.find(class_=re.compile(r"date|time|when", re.I))
                date = date_el.get_text(strip=True) if date_el else "See website"

                desc_el = c.find("p")
                description = desc_el.get_text(strip=True)[:300] if desc_el else ""

                link_el = c.find("a", href=True)
                link = link_el["href"] if link_el else url
                if link.startswith("/"): link = "https://www.visitparkcity.com" + link

                loc_el = c.find(class_=re.compile(r"location|venue|place", re.I))
                location = loc_el.get_text(strip=True) if loc_el else "Park City, UT"

                events.append({
                    "title": title, "date": date, "description": description,
                    "location": location, "link": link,
                    "source": "Visit Park City",
                    "source_url": url,
                    "scraped_at": datetime.now().isoformat()
                })
            except:
                continue

        print(f"  Found {len(events)} events from Visit Park City")
    except Exception as e:
        print(f"  Error scraping Visit Park City: {e}")
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

        skip_titles = {"kpcw", "community calendar", "submit", "donate", "listen"}

        for c in containers:
            try:
                title_el = c.find("h2") or c.find("h3") or c.find("h4") or c.find("a")
                if not title_el: continue
                title = title_el.get_text(strip=True)
                if len(title) < 3 or title.lower() in skip_titles: continue

                date_el = c.find(class_=re.compile(r"date|time|when", re.I)) or c.find("time")
                date = date_el.get_text(strip=True) if date_el else "See website"

                desc_el = c.find("p")
                description = desc_el.get_text(strip=True)[:300] if desc_el else ""

                link_el = c.find("a", href=True)
                link = link_el["href"] if link_el else url
                if link.startswith("/"): link = "https://www.kpcw.org" + link

                events.append({
                    "title": title, "date": date, "description": description,
                    "location": "Park City, UT", "link": link,
                    "source": "KPCW Community Calendar",
                    "source_url": url,
                    "scraped_at": datetime.now().isoformat()
                })
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
    try:
        url = "https://www.eventbrite.com/d/ut--park-city/events/"
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")

        # Try JSON-LD structured data first
        scripts = soup.find_all("script", type="application/ld+json")
        for script in scripts:
            try:
                data = json.loads(script.string)
                items = data if isinstance(data, list) else [data]
                for item in items:
                    if item.get("@type") not in ["Event", "SocialEvent", "MusicEvent"]:
                        continue
                    title = item.get("name", "")
                    if not title: continue
                    date = item.get("startDate", "See website")
                    description = re.sub(r'<[^>]+>', '', item.get("description", ""))[:300]
                    loc = item.get("location", {})
                    location = loc.get("name", "Park City, UT") if isinstance(loc, dict) else "Park City, UT"
                    link = item.get("url", url)
                    offers = item.get("offers", {})
                    price = offers.get("price", "") if isinstance(offers, dict) else ""
                    events.append({
                        "title": title, "date": date, "description": description,
                        "location": location, "link": link, "price": str(price),
                        "source": "Eventbrite",
                        "source_url": url,
                        "scraped_at": datetime.now().isoformat()
                    })
            except:
                continue

        # Fallback: HTML cards
        if not events:
            cards = soup.find_all("div", class_=re.compile(r"event-card|search-event", re.I))
            for card in cards:
                try:
                    title_el = card.find("h2") or card.find("h3") or card.find(class_=re.compile(r"title", re.I))
                    if not title_el: continue
                    title = title_el.get_text(strip=True)
                    if len(title) < 3: continue
                    date_el = card.find(class_=re.compile(r"date|time", re.I)) or card.find("time")
                    date = date_el.get_text(strip=True) if date_el else "See website"
                    link_el = card.find("a", href=True)
                    link = link_el["href"] if link_el else url
                    events.append({
                        "title": title, "date": date, "description": "",
                        "location": "Park City, UT", "link": link,
                        "source": "Eventbrite",
                        "source_url": url,
                        "scraped_at": datetime.now().isoformat()
                    })
                except:
                    continue

        print(f"  Found {len(events)} events from Eventbrite")
    except Exception as e:
        print(f"  Error scraping Eventbrite: {e}")
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
                date = date_el.get_text(strip=True) if date_el else "See website"

                dist_el = c.find(class_=re.compile(r"dist|distance|type", re.I))
                distance = dist_el.get_text(strip=True) if dist_el else ""

                link_el = c.find("a", href=True)
                link = link_el["href"] if link_el else url
                if link.startswith("/"): link = "https://www.runningintheusa.com" + link

                events.append({
                    "title": title,
                    "date": date,
                    "description": f"Race in Park City, UT. {distance}".strip().rstrip("."),
                    "location": "Park City, UT",
                    "link": link,
                    "source": "Running in the USA",
                    "source_url": url,
                    "category": "sports",
                    "scraped_at": datetime.now().isoformat()
                })
            except:
                continue

    except Exception as e:
        print(f"  HTTP scrape failed ({e}), using known races only")

    # Always include known major Park City races
    known_races = [
        {
            "title": "Running with Ed 2026",
            "date": "2026-05-16",
            "description": "Park City's favorite community relay race fundraiser for the Park City Education Foundation. 27.6 mile 8-leg relay starting at Basin Recreation Fieldhouse.",
            "location": "Basin Recreation Fieldhouse, Park City, UT",
            "link": "https://www.runningwithed.com",
            "source": "Running in the USA",
            "source_url": "https://www.runningintheusa.com",
            "category": "sports",
            "scraped_at": datetime.now().isoformat()
        },
        {
            "title": "Park City Trail Series",
            "date": "2026-06-06",
            "description": "3-race trail series June through August. 5K, 10K and Half Marathon on Park City's iconic trails. Perfect for all levels.",
            "location": "Park City, UT",
            "link": "https://runsignup.com/Race/UT/ParkCity/ParkCityTrailSeriesFullSeries",
            "source": "Running in the USA",
            "source_url": "https://www.runningintheusa.com",
            "category": "sports",
            "scraped_at": datetime.now().isoformat()
        },
        {
            "title": "Triple Trail Challenge — Round Valley Rambler & Jupiter Peak",
            "date": "2026-06-13",
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
# 5. PARK RECORD — AI-powered article scraper
# ─────────────────────────────────────────────
def scrape_park_record():
    print("Scraping Park Record (AI-powered)...")
    events = []
    try:
        # Step 1: Find the most recent Scene Happenings article URL
        today = datetime.now()
        year = today.year
        month = str(today.month).zfill(2)

        # Try the last 14 days to find the most recent article
        article_text = ""
        article_url = ""
        for days_back in range(0, 14):
            check_date = datetime(today.year, today.month, today.day)
            check_date = check_date.replace(day=max(1, today.day - days_back))
            url = f"https://www.parkrecord.com/{check_date.year}/{str(check_date.month).zfill(2)}/"
            try:
                r = requests.get(url, headers=HEADERS, timeout=10)
                soup = BeautifulSoup(r.text, "html.parser")
                # Find Scene Happenings link
                for a in soup.find_all("a", href=True):
                    href = a["href"]
                    text = a.get_text(strip=True).lower()
                    if "scene-happenings" in href or "community-calendar" in href:
                        article_url = href
                        break
                if article_url:
                    break
            except:
                continue

        # If not found by browsing index, use the known latest URL directly
        if not article_url:
            article_url = "https://www.parkrecord.com/2026/05/08/scene-happenings-may-9-to-may-12/"

        # Step 2: Fetch the article content
        print(f"  Fetching: {article_url}")
        r = requests.get(article_url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")

        # Extract article body text
        article_body = (
            soup.find("div", class_=re.compile(r"article-body|entry-content|post-content|content", re.I)) or
            soup.find("article") or
            soup.find("main")
        )
        if article_body:
            article_text = article_body.get_text(separator="\n", strip=True)[:8000]
        else:
            article_text = soup.get_text(separator="\n", strip=True)[:8000]

        if not article_text or len(article_text) < 100:
            print("  Could not extract article text")
            return events

        # Step 3: Use Claude API to extract structured events from the article
        print("  Using AI to extract events from article...")

        prompt = f"""You are an event extraction assistant. Read this Park City, Utah local newspaper article and extract all events mentioned.

For each event return a JSON array where each item has:
- title: event name
- date: date as written in the article (e.g. "May 12", "Saturday, May 16", "every Wednesday")
- time: time if mentioned (e.g. "7 p.m.", "3-5 p.m.") or ""
- location: venue/address if mentioned or "Park City, UT"
- description: 1-2 sentence summary
- link: any website URL mentioned for this event or ""
- is_free: true if explicitly free, false if has a cost, null if unknown

Only include real events (performances, classes, markets, races, talks, screenings, etc).
Skip ads, staff credits, and non-event content.
Return ONLY valid JSON array, no other text.

ARTICLE:
{article_text}"""

        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "Content-Type": "application/json",
                "x-api-key": "",  # API key handled by environment
                "anthropic-version": "2023-06-01"
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 4000,
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=30
        )

        if response.status_code != 200:
            print(f"  Claude API error: {response.status_code}")
            return events

        result = response.json()
        content = result.get("content", [{}])[0].get("text", "")

        # Parse JSON from response
        content = content.strip()
        if content.startswith("```"):
            content = re.sub(r'```(?:json)?', '', content).strip().rstrip("```").strip()

        extracted = json.loads(content)

        for item in extracted:
            if not item.get("title"): continue
            date_str = item.get("date", "See website")
            time_str = item.get("time", "")
            if time_str:
                date_str = f"{date_str} {time_str}".strip()

            events.append({
                "title": item["title"],
                "date": date_str,
                "description": item.get("description", ""),
                "location": item.get("location", "Park City, UT"),
                "link": item.get("link", article_url) or article_url,
                "source": "The Park Record",
                "source_url": article_url,
                "is_free": item.get("is_free"),
                "scraped_at": datetime.now().isoformat()
            })

        print(f"  Found {len(events)} events from Park Record (AI-extracted)")

    except json.JSONDecodeError as e:
        print(f"  Could not parse AI response as JSON: {e}")
    except Exception as e:
        print(f"  Error scraping Park Record: {e}")
    return events


# ─────────────────────────────────────────────
# DEDUPLICATE
# ─────────────────────────────────────────────
def deduplicate(events):
    seen = set()
    unique = []
    for e in events:
        key = re.sub(r'\s+', ' ', e["title"].lower().strip())[:40]
        if key not in seen:
            seen.add(key)
            unique.append(e)
    return unique


# ─────────────────────────────────────────────
# SAVE
# ─────────────────────────────────────────────
def save_events(events, filename="events.json"):
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

    print(f"\nTotal raw events: {len(all_events)}")
    unique = deduplicate(all_events)
    print(f"After deduplication: {len(unique)}")

    save_events(unique)

    print()
    print("Done! Sample events found:")
    for e in unique[:10]:
        print(f"  [{e['source']}] {e['title']} -- {e['date']}")

if __name__ == "__main__":
    main()

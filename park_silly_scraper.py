"""Park Silly Sunday Market scraper.

Park Silly publishes the season's market dates on their homepage as a
free-text block, e.g. "2026 SUMMER DATES — June 7, 14, 21, 28 — July 12, 19
— August 30 — September 6, 13, 20, 27 — Market Hours: 10am - 5pm".

This scraper fetches the homepage, parses the date block, and emits one
event per market date.

Resilience:
  - Looks for "SUMMER DATES" or "MARKET DATES" or "2026" near a date list.
  - Handles "June 7, 14, 21, 28" by remembering the most recent month name.
  - Falls back gracefully if the page can't be parsed: returns [] and logs.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import List

import requests


HOMEPAGE = "https://www.parksillysundaymarket.com/"
PARK_CITY_LAT = 40.6461
PARK_CITY_LNG = -111.4980

MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5,
    "june": 6, "july": 7, "august": 8, "september": 9, "october": 10,
    "november": 11, "december": 12,
}


def _strip_html(html: str) -> str:
    """Strip script/style/tags, decode common entities, collapse whitespace."""
    import html as html_lib
    html = re.sub(r"<script.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<style.*?</style>",  "", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", html)
    text = html_lib.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _parse_dates(text: str, target_year: int) -> List[date]:
    """Parse "June 7, 14, 21, 28 July 12, 19 August 30 September 6, 13, 20, 27"
    into a list of date objects in target_year. Tracks the current month as
    it walks left-to-right; resets it on each month-name match."""
    # Restrict to the season-dates window: from "DATES" up to "Market Hours" or
    # "Rain or Shine" — keeps us out of unrelated date mentions elsewhere on
    # the page.
    block = text
    m_start = re.search(r"(?:summer|market)\s+dates", text, re.IGNORECASE)
    if m_start:
        block = text[m_start.end(): m_start.end() + 400]
    m_end = re.search(r"(?:market\s+hours|rain\s+or\s+shine|hours\s*:)", block, re.IGNORECASE)
    if m_end:
        block = block[: m_end.start()]

    out: List[date] = []
    current_month: int | None = None
    # Tokenize the block: month-names, day-numbers, ignore commas
    for tok in re.findall(r"[A-Za-z]+|\d+", block):
        low = tok.lower()
        if low in MONTHS:
            current_month = MONTHS[low]
            continue
        if current_month and tok.isdigit():
            day = int(tok)
            if 1 <= day <= 31:
                try:
                    out.append(date(target_year, current_month, day))
                except ValueError:
                    pass
    return out


def _parse_hours(text: str) -> tuple[str, str]:
    """Parse 'Market Hours: 10am - 5pm' -> ('10:00 AM', '5:00 PM')."""
    m = re.search(
        r"market\s+hours\s*:?\s*(\d{1,2})\s*(am|pm)?\s*[-\u2013]\s*(\d{1,2})\s*(am|pm)",
        text, re.IGNORECASE,
    )
    if not m:
        return ("10:00 AM", "5:00 PM")  # historical default
    sh = int(m.group(1)); s_ampm = (m.group(2) or "AM").upper()
    eh = int(m.group(3)); e_ampm = m.group(4).upper()
    if s_ampm == "AM" and (m.group(2) is None) and eh < sh:
        s_ampm = "AM"  # 10 - 5pm → 10am - 5pm
    return (f"{sh}:00 {s_ampm}", f"{eh}:00 {e_ampm}")


def scrape_park_silly() -> list:
    """Fetch and parse the Park Silly homepage. Return one event per market date."""
    print("Scraping Park Silly Sunday Market (homepage)...")
    try:
        r = requests.get(HOMEPAGE, timeout=20, headers={
            "User-Agent": "Mozilla/5.0 yoocal-bot/1.0",
        })
        r.raise_for_status()
    except Exception as ex:
        print(f"  [Park Silly] fetch failed: {ex}")
        return []

    text = _strip_html(r.text)

    # Find the year from "2026 SUMMER DATES" or similar
    year_match = re.search(r"(20\d\d)\s*(?:summer|market)\s+dates", text, re.IGNORECASE)
    if not year_match:
        # Fallback: pull the largest 4-digit year near a "dates" phrase
        m = re.search(r"(?:summer|market)\s+dates", text, re.IGNORECASE)
        if m:
            year_window = text[max(0, m.start() - 50): m.start() + 200]
            ys = re.findall(r"20\d\d", year_window)
            year = max(int(y) for y in ys) if ys else date.today().year
        else:
            year = date.today().year
    else:
        year = int(year_match.group(1))
    print(f"  [Park Silly] season year: {year}")

    dates = _parse_dates(text, year)
    if not dates:
        print(f"  [Park Silly] no dates parsed from homepage")
        return []

    start_time, end_time = _parse_hours(text)
    print(f"  [Park Silly] {len(dates)} market dates, hours {start_time} – {end_time}")

    description = (
        "Open-air market, street festival, and community forum on Historic "
        "Main Street. Local vendors, food, live music, and family activities. "
        "Free admission, dog-friendly. Rain or shine."
    )

    today_iso = datetime.now().strftime("%Y-%m-%d")
    events = []
    for d in dates:
        ev = {
            "title": "Park Silly Sunday Market",
            "date": d.isoformat(),
            "start_time": start_time,
            "end_time": end_time,
            "description": description,
            "location": "Main Street, Park City, UT",
            "venue_name": "Main Street",
            "address": "Main Street, Park City, UT 84060",
            "link": HOMEPAGE,
            "source": "Park Silly Sunday Market",
            "source_url": HOMEPAGE,
            "categories": ["Outdoor", "Food & Drink", "Music", "Community"],
            "lat": PARK_CITY_LAT,
            "lng": PARK_CITY_LNG,
            "scraped_at": datetime.now().isoformat(),
        }
        if ev["date"] >= today_iso:
            events.append(ev)
    return events


if __name__ == "__main__":
    events = scrape_park_silly()
    print(f"\n=== {len(events)} future events ===")
    for e in events:
        print(f"  {e['date']} {e['start_time']} - {e['end_time']} | {e['title']}")

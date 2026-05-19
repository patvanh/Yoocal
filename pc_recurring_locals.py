"""Hand-curated recurring Park City events.

For known annuals, weekly institutions, and signature events that aren't
reliably surfaced by any automated source (Song Summit, certain festivals,
specific venues with no parseable calendar, etc.).

Each entry is a dict with at minimum:
  - title, date (YYYY-MM-DD), location, link, source
Optional:
  - end_date, start_time, end_time, description, categories, venue_name,
    address, lat, lng

Recurring institutions use one of these patterns:
  - dates              : ["2026-06-07", "2026-06-14", ...]  (explicit list)
  - recurrence_day     : "Wednesday"                          (one weekday)
  - recurrence_days    : "Monday,Wednesday,Friday"            (multiple weekdays)
  - recurrence         : "daily" | "monthly_last_friday"      (special patterns)
All non-explicit patterns require season_start and season_end.
"""
from __future__ import annotations

from datetime import datetime

PARK_CITY_LAT = 40.6461
PARK_CITY_LNG = -111.4980


_ANNUAL_EVENTS = [
    {
        "title": "Park City Song Summit 2026",
        "date": "2026-08-27",
        "end_date": "2026-08-29",
        "start_time": "4:30 PM",
        "description": (
            "Three-day songwriter festival with songwriter rounds, supper "
            "clubs, wellness sessions, live podcasts, and headliner shows. "
            "2026 lineup includes Sierra Hull, Steve Poltz, Jim James "
            "(acoustic), Mountain Jam featuring members of My Morning "
            "Jacket, Eric Krasno, Ivan Neville, and more. Free village "
            "programming at Library Field plus ticketed evening shows at "
            "The Marquis."
        ),
        "location": "Library Field & venues across Park City, UT",
        "link": "https://songsummit.com/pages/schedule",
        "source": "Park City Song Summit",
        "source_url": "https://songsummit.com",
        "categories": ["Music", "Festival"],
        "venue_name": "Park City Song Summit",
        "address": "1255 Park Ave, Park City, UT 84060",
        "lat": PARK_CITY_LAT,
        "lng": PARK_CITY_LNG,
    },
    {
        "title": "Park City 4th of July Parade & Fireworks",
        "date": "2026-07-04",
        "start_time": "11:00 AM",
        "description": (
            "Annual Independence Day celebration. Morning parade down Main "
            "Street with floats, marching bands, and local groups. Evening "
            "fireworks over Park City. Family-friendly and free to attend."
        ),
        "location": "Main Street, Park City, UT",
        "link": "https://www.visitparkcity.com/events/4th-of-july/",
        "source": "Park City Annual Events",
        "source_url": "https://www.visitparkcity.com/",
        "categories": ["Community", "Family", "Free"],
        "venue_name": "Main Street",
        "address": "Main Street, Park City, UT 84060",
        "lat": PARK_CITY_LAT,
        "lng": PARK_CITY_LNG,
    },
    {
        "title": "Kimball Arts Festival 2026",
        "date": "2026-08-07",
        "end_date": "2026-08-09",
        "start_time": "10:00 AM",
        "description": (
            "Three-day juried fine arts and crafts festival on Main Street "
            "presented by the Kimball Art Center. 200+ artists, live music, "
            "food, and family activities. Park City's largest summer arts "
            "event. Confirm exact dates at kimballartcenter.org."
        ),
        "location": "Main Street, Park City, UT",
        "link": "https://www.kimballartcenter.org/arts-festival/",
        "source": "Park City Annual Events",
        "source_url": "https://www.kimballartcenter.org/",
        "categories": ["Arts", "Festival", "Family"],
        "venue_name": "Main Street",
        "address": "Main Street, Park City, UT 84060",
        "lat": PARK_CITY_LAT,
        "lng": PARK_CITY_LNG,
    },
    {
        "title": "Miners Day Parade & Mucking and Drilling Competition",
        "date": "2026-09-07",
        "start_time": "11:00 AM",
        "description": (
            "Park City's beloved Labor Day tradition honoring the town's "
            "mining heritage. Main Street parade followed by the historic "
            "mucking and drilling competition at City Park. Free, family "
            "friendly, classic Park City."
        ),
        "location": "Main Street & City Park, Park City, UT",
        "link": "https://www.visitparkcity.com/events/miners-day/",
        "source": "Park City Annual Events",
        "source_url": "https://www.visitparkcity.com/",
        "categories": ["Community", "Family", "Free"],
        "venue_name": "Main Street",
        "address": "Main Street, Park City, UT 84060",
        "lat": PARK_CITY_LAT,
        "lng": PARK_CITY_LNG,
    },
    {
        "title": "Autumn Aloft Hot Air Balloon Festival",
        "date": "2026-09-19",
        "end_date": "2026-09-20",
        "start_time": "7:00 AM",
        "description": (
            "Annual mid-September hot air balloon festival at the North 40 "
            "fields. Dawn launches both mornings, plus a Saturday night "
            "balloon glow. Free to watch. Bring coffee — launches are early."
        ),
        "location": "North 40 Fields, Park City, UT",
        "link": "https://www.autumnaloft.com/",
        "source": "Park City Annual Events",
        "source_url": "https://www.autumnaloft.com/",
        "categories": ["Outdoor", "Family", "Free"],
        "venue_name": "North 40 Fields",
        "address": "North 40 Fields, Park City, UT 84060",
        "lat": PARK_CITY_LAT,
        "lng": PARK_CITY_LNG,
    },
    {
        "title": "Howl-O-Ween Dog Parade",
        "date": "2026-10-31",
        "start_time": "12:00 PM",
        "description": (
            "Costumed dog parade down Main Street. Locals dress up their "
            "pups (and themselves) for Halloween. Awards for best costume. "
            "Free, family-friendly, one of Park City's most photographed "
            "annual traditions."
        ),
        "location": "Main Street, Park City, UT",
        "link": "https://www.visitparkcity.com/events/",
        "source": "Park City Annual Events",
        "source_url": "https://www.visitparkcity.com/",
        "categories": ["Community", "Family", "Free"],
        "venue_name": "Main Street",
        "address": "Main Street, Park City, UT 84060",
        "lat": PARK_CITY_LAT,
        "lng": PARK_CITY_LNG,
    },
    {
        "title": "Electric Parade & Holiday Tree Lighting",
        "date": "2026-12-05",
        "start_time": "6:00 PM",
        "description": (
            "Park City's holiday season kickoff. Electric Parade down Main "
            "Street featuring lit floats and the historic tree lighting at "
            "Miners Park. Hot cocoa, carolers, Santa. Free, family-friendly. "
            "Confirm exact date at visitparkcity.com — typically the first "
            "Saturday of December."
        ),
        "location": "Main Street, Park City, UT",
        "link": "https://www.visitparkcity.com/events/electric-parade/",
        "source": "Park City Annual Events",
        "source_url": "https://www.visitparkcity.com/",
        "categories": ["Community", "Family", "Free"],
        "venue_name": "Main Street",
        "address": "Main Street, Park City, UT 84060",
        "lat": PARK_CITY_LAT,
        "lng": PARK_CITY_LNG,
    },
]


_RECURRING_INSTITUTIONS = [
    {
        "title": "Last Friday Gallery Stroll",
        "recurrence": "monthly_last_friday",
        "season_start": "2026-05-29",
        "season_end": "2026-12-31",
        "start_time": "6:00 PM",
        "end_time": "9:00 PM",
        "description": (
            "Free monthly gallery stroll on the last Friday of every month "
            "on Historic Main Street. Park City's galleries open their "
            "doors with refreshments, openings, and artist receptions."
        ),
        "location": "Main Street, Park City, UT",
        "venue_name": "Main Street",
        "address": "Main Street, Park City, UT 84060",
        "link": "https://www.parkcitygalleryassociation.com/",
        "source": "Park City Gallery Association",
        "source_url": "https://www.parkcitygalleryassociation.com/",
        "categories": ["Arts", "Community"],
        "lat": PARK_CITY_LAT,
        "lng": PARK_CITY_LNG,
    },
    {
        "title": "Group Fitness Classes at Park City Athletic & Rec Center",
        "recurrence_days": "Monday,Tuesday,Wednesday,Thursday,Friday,Saturday",
        "season_start": "2026-05-19",
        "season_end": "2026-12-31",
        "start_time": "6:00 AM",
        "end_time": "8:00 PM",
        "description": (
            "Drop-in group fitness classes — yoga, spin, HIIT, strength, "
            "Pilates, and more — Mon-Sat at the Park City Municipal Athletic "
            "& Recreation Center. Schedule varies by day; visit website."
        ),
        "location": "Park City Municipal Athletic & Recreation Center, Park City, UT",
        "venue_name": "Park City Municipal Athletic & Recreation Center",
        "address": "1354 Park Ave, Park City, UT 84060",
        "link": "https://www.visitparkcity.com/event/group-fitness-classes/",
        "source": "Park City Annual Events",
        "source_url": "https://www.visitparkcity.com/",
        "categories": ["Wellness", "Sports"],
        "lat": PARK_CITY_LAT,
        "lng": PARK_CITY_LNG,
    },
    {
        "title": "PLUNJ Park City — Cold Plunge & Wellness",
        "recurrence": "daily",
        "season_start": "2026-05-19",
        "season_end": "2026-12-31",
        "start_time": "9:00 AM",
        "end_time": "8:00 PM",
        "description": (
            "Daily cold plunge and contrast therapy at PLUNJ Park City. "
            "Drop-in sessions and memberships."
        ),
        "location": "PLUNJ Park City, Park City, UT",
        "venue_name": "PLUNJ Park City",
        "address": "Park City, UT 84060",
        "link": "https://www.plunj.com/",
        "source": "Park City Annual Events",
        "source_url": "https://www.plunj.com/",
        "categories": ["Wellness"],
        "lat": PARK_CITY_LAT,
        "lng": PARK_CITY_LNG,
    },
    {
        "title": "Fascia Rolling Class at Rise Dental Wellness",
        "recurrence_day": "Monday",
        "season_start": "2026-05-25",
        "season_end": "2026-10-26",
        "start_time": "5:30 PM",
        "end_time": "6:30 PM",
        "description": (
            "Weekly Monday fascia rolling and bodywork class at Rise Dental "
            "Wellness. Drop-in friendly."
        ),
        "location": "Rise Dental Wellness, Park City, UT",
        "venue_name": "Rise Dental Wellness",
        "address": "Park City, UT 84060",
        "link": "https://www.risedentalwellness.com/",
        "source": "Park City Annual Events",
        "source_url": "https://www.risedentalwellness.com/",
        "categories": ["Wellness"],
        "lat": PARK_CITY_LAT,
        "lng": PARK_CITY_LNG,
    },
    {
        "title": "Park Silly Sunday Market",
        "dates": [
            "2026-06-07", "2026-06-14", "2026-06-21", "2026-06-28",
            "2026-07-12", "2026-07-19",
            "2026-08-30",
            "2026-09-06", "2026-09-13", "2026-09-20", "2026-09-27",
        ],
        "start_time": "10:00 AM",
        "end_time": "5:00 PM",
        "description": (
            "Open-air market, street festival, and community forum on "
            "Historic Main Street. Local vendors, food, live music, and "
            "family activities. Free admission, dog-friendly. Rain or shine."
        ),
        "location": "Main Street, Park City, UT",
        "venue_name": "Main Street",
        "address": "Main Street, Park City, UT 84060",
        "link": "https://www.parksillysundaymarket.com/",
        "source": "Park Silly Sunday Market",
        "source_url": "https://www.parksillysundaymarket.com/",
        "categories": ["Outdoor", "Food & Drink", "Music", "Community"],
        "lat": PARK_CITY_LAT,
        "lng": PARK_CITY_LNG,
    },
    {
        "title": "Park City Farmers Market",
        "recurrence_day": "Wednesday",
        "season_start": "2026-05-27",
        "season_end": "2026-10-21",
        "start_time": "11:00 AM",
        "end_time": "5:00 PM",
        "description": (
            "Weekly outdoor farmers market at Park City Mountain Resort. "
            "Local produce, baked goods, prepared food, artisans, and "
            "live music. Dog-friendly. Free admission."
        ),
        "location": "Park City Mountain Resort base, 1345 Lowell Ave, Park City, UT",
        "venue_name": "Park City Mountain Resort base",
        "address": "1345 Lowell Ave, Park City, UT 84060",
        "link": "https://parkcityfarmersmarket.com/",
        "source": "Park City Farmers Market",
        "source_url": "https://parkcityfarmersmarket.com/",
        "categories": ["Food & Drink", "Outdoor", "Community"],
        "lat": 40.6514,
        "lng": -111.5076,
    },
]


_DOW = {"Monday": 0, "Tuesday": 1, "Wednesday": 2, "Thursday": 3,
        "Friday": 4, "Saturday": 5, "Sunday": 6}


def _expand_recurring(rec: dict) -> list:
    """Expand a recurring institution into per-occurrence records.

    Patterns:
      A. Explicit dates list   ('dates')
      B. Weekly single day     ('recurrence_day')
      C. Weekly multiple days  ('recurrence_days' as CSV)
      D. Daily                 ('recurrence' = 'daily')
      E. Monthly last Friday   ('recurrence' = 'monthly_last_friday')
    """
    from datetime import date, timedelta
    from calendar import monthrange

    # Pattern A: explicit dates list
    if "dates" in rec:
        out = []
        for d in rec["dates"]:
            ev = {k: v for k, v in rec.items() if k != "dates"}
            ev["date"] = d
            ev["scraped_at"] = datetime.now().isoformat()
            out.append(ev)
        return out

    try:
        start = date.fromisoformat(rec["season_start"])
        end = date.fromisoformat(rec["season_end"])
    except (KeyError, ValueError):
        return []

    recurrence = rec.get("recurrence", "")
    out = []

    # Pattern B: weekly single day
    if rec.get("recurrence_day"):
        target_dow = _DOW.get(rec["recurrence_day"])
        if target_dow is None:
            return []
        cur = start
        while cur <= end:
            if cur.weekday() == target_dow:
                ev = {k: v for k, v in rec.items()
                      if k not in ("recurrence_day", "season_start", "season_end", "recurrence")}
                ev["date"] = cur.isoformat()
                ev["scraped_at"] = datetime.now().isoformat()
                out.append(ev)
            cur += timedelta(days=1)
        return out

    # Pattern C: weekly multiple days
    if rec.get("recurrence_days"):
        days_set = set(
            _DOW[d.strip()] for d in rec["recurrence_days"].split(",")
            if d.strip() in _DOW
        )
        cur = start
        while cur <= end:
            if cur.weekday() in days_set:
                ev = {k: v for k, v in rec.items()
                      if k not in ("recurrence_days", "season_start", "season_end", "recurrence")}
                ev["date"] = cur.isoformat()
                ev["scraped_at"] = datetime.now().isoformat()
                out.append(ev)
            cur += timedelta(days=1)
        return out

    # Pattern D: daily
    if recurrence == "daily":
        cur = start
        while cur <= end:
            ev = {k: v for k, v in rec.items()
                  if k not in ("season_start", "season_end", "recurrence")}
            ev["date"] = cur.isoformat()
            ev["scraped_at"] = datetime.now().isoformat()
            out.append(ev)
            cur += timedelta(days=1)
        return out

    # Pattern E: monthly last Friday
    if recurrence == "monthly_last_friday":
        cur_year = start.year
        cur_month = start.month
        while True:
            last_day = monthrange(cur_year, cur_month)[1]
            last_date = date(cur_year, cur_month, last_day)
            offset = (last_date.weekday() - 4) % 7  # 4 = Friday
            last_friday = last_date - timedelta(days=offset)
            if last_friday > end:
                break
            if last_friday >= start:
                ev = {k: v for k, v in rec.items()
                      if k not in ("season_start", "season_end", "recurrence")}
                ev["date"] = last_friday.isoformat()
                ev["scraped_at"] = datetime.now().isoformat()
                out.append(ev)
            cur_month += 1
            if cur_month > 12:
                cur_month = 1
                cur_year += 1
        return out

    return []


def scrape_recurring_locals() -> list:
    """Return all hand-curated recurring Park City events."""
    print("Scraping recurring locals (hand-curated)...")
    events = []

    for ev in _ANNUAL_EVENTS:
        e = dict(ev)
        e["scraped_at"] = datetime.now().isoformat()
        events.append(e)

    for rec in _RECURRING_INSTITUTIONS:
        events.extend(_expand_recurring(rec))

    today_iso = datetime.now().strftime("%Y-%m-%d")
    events = [e for e in events
              if (e.get("end_date") or e.get("date", "")) >= today_iso]

    print(f"  [recurring_locals] {len(events)} events")
    return events


if __name__ == "__main__":
    events = scrape_recurring_locals()
    print()
    from collections import Counter
    titles = Counter(e["title"] for e in events)
    print(f"Total: {len(events)}, unique titles: {len(titles)}")
    print("\nBy title:")
    for t, n in titles.most_common():
        print(f"  {n:4d}x  {t[:60]}")

"""Hand-curated recurring Park City events.

For known annuals, weekly institutions, and signature events that aren't
reliably surfaced by any automated source (Song Summit, certain festivals,
specific venues with no parseable calendar, etc.).

Each entry is a dict with at minimum:
  - title, date (YYYY-MM-DD), location, link, source
Optional:
  - end_date, start_time, end_time, description, categories, venue_name,
    address, lat, lng

Weekly/biweekly recurring events use `recurrence_day` (e.g. "Sunday") or
`recurrence_days` (CSV "Sunday,Wednesday") plus a date range. The frontend
filter at CalendarClient.tsx line ~261 expands these into per-day views.
"""
from __future__ import annotations

from datetime import datetime

PARK_CITY_LAT = 40.6461
PARK_CITY_LNG = -111.4980


# ---- Annual signature events ----
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
]


# ---- Weekly / biweekly recurring institutions ----
# Each gets expanded into per-day records in expand_recurring().
_RECURRING_INSTITUTIONS = [
    {
        # 2026 season verified at parkcityfarmersmarket.com (Grand Opening
        # May 27, runs every Wednesday through October). Confirm dates each
        # spring — they publish on their WordPress blog.
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
    """Expand a recurring institution into per-week event records."""
    from datetime import date, timedelta
    try:
        start = date.fromisoformat(rec["season_start"])
        end = date.fromisoformat(rec["season_end"])
    except (KeyError, ValueError):
        return []
    target_dow = _DOW.get(rec.get("recurrence_day", ""))
    if target_dow is None:
        return []

    out = []
    cur = start
    while cur <= end:
        if cur.weekday() == target_dow:
            ev = {k: v for k, v in rec.items()
                  if k not in ("recurrence_day", "season_start", "season_end")}
            ev["date"] = cur.isoformat()
            ev["scraped_at"] = datetime.now().isoformat()
            out.append(ev)
        cur += timedelta(days=1)
    return out


def scrape_recurring_locals() -> list:
    """Return all hand-curated recurring Park City events."""
    print("Scraping recurring locals (hand-curated)...")
    events = []

    # Annuals — copy and stamp scraped_at
    for ev in _ANNUAL_EVENTS:
        e = dict(ev)
        e["scraped_at"] = datetime.now().isoformat()
        events.append(e)

    # Recurring institutions — expand into per-week instances
    for rec in _RECURRING_INSTITUTIONS:
        events.extend(_expand_recurring(rec))

    # Drop past events
    today_iso = datetime.now().strftime("%Y-%m-%d")
    events = [e for e in events
              if (e.get("end_date") or e.get("date", "")) >= today_iso]

    print(f"  [recurring_locals] {len(events)} events")
    return events


if __name__ == "__main__":
    events = scrape_recurring_locals()
    print()
    for e in sorted(events, key=lambda x: x["date"]):
        print(f"  {e['date']} {e.get('start_time') or '--':<8} | {e['title'][:55]}")

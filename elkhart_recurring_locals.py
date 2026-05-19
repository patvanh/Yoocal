"""Hand-curated Elkhart Lake annual & signature events.

Sourced from the official "Elkhart Lake 2026 Major Events" poster
published by the Elkhart Lake tourism office. These are flagship local
events that we want guaranteed coverage of, even if Tribe API, Road
America, Siebkens, or Osthoff calendars miss them or publish late.

Yearly maintenance: replace this file's 2026 dates with the next year's
when the new poster comes out (typically February/March). Most events
recur in the same week or weekend each year.
"""
from __future__ import annotations

from datetime import datetime


ELKHART_LAT = 43.8347
ELKHART_LNG = -88.0398


# Each dict: title, date (or date+end_date for multi-day), location, link,
# source ("Elkhart Lake Tourism"), categories, description.
_ANNUAL_EVENTS = [
    {
        "title": "Shop & Sip",
        "date": "2026-04-25",
        "location": "Elkhart Lake Retail Shops, Elkhart Lake, WI",
        "venue_name": "Elkhart Lake Retail Shops",
        "description": (
            "Browse Elkhart Lake's boutique retail shops while sipping local "
            "beverages. Annual spring shopping event in downtown."
        ),
        "categories": ["Community", "Food & Drink"],
    },
    {
        "title": "Jazz on the Vine",
        "date": "2026-05-01",
        "end_date": "2026-05-02",
        "location": "The Osthoff Resort, Elkhart Lake, WI",
        "venue_name": "The Osthoff Resort",
        "description": (
            "Annual jazz festival at The Osthoff Resort. Two days of live jazz "
            "performances paired with wine, fine dining, and lakeside ambiance."
        ),
        "categories": ["Music", "Festival", "Food & Drink"],
    },
    {
        "title": "24 Hours of Lemons Block Party",
        "date": "2026-05-08",
        "location": "Siebkens Resort, Elkhart Lake, WI",
        "venue_name": "Siebkens Resort",
        "description": (
            "Block party at Siebkens during the 24 Hours of Lemons race weekend "
            "at Road America. Live music, food, and racing camaraderie."
        ),
        "categories": ["Community", "Music", "Sports"],
    },
    {
        "title": "Mother's Day Brunch",
        "date": "2026-05-10",
        "location": "The Osthoff Resort & Road America, Elkhart Lake, WI",
        "description": (
            "Mother's Day brunch service at The Osthoff Resort and Road America. "
            "Reservations recommended."
        ),
        "categories": ["Food & Drink", "Family"],
    },
    {
        "title": "Spring Vintage Weekend with SVRA",
        "date": "2026-05-15",
        "end_date": "2026-05-17",
        "location": "Road America, Elkhart Lake, WI",
        "venue_name": "Road America",
        "description": (
            "SVRA Sportscar Vintage Racing Association spring weekend at Road "
            "America. Vintage race cars on the historic 4-mile road course."
        ),
        "categories": ["Sports", "Outdoor"],
    },
    {
        "title": "Farmers & Artisans Market (Season Opening)",
        "date": "2026-05-23",
        "end_date": "2026-10-03",
        "start_time": "8:00 AM",
        "location": "Elkhart Lake Depot & Village Square, Elkhart Lake, WI",
        "venue_name": "Elkhart Lake Depot & Village Square",
        "description": (
            "Weekly Saturday farmers and artisans market running May 23 through "
            "October 3. Local produce, baked goods, crafts, and live music. "
            "Family-friendly and free."
        ),
        "categories": ["Outdoor", "Food & Drink", "Community"],
    },
    {
        "title": "The Hard Left Moto Show",
        "date": "2026-05-30",
        "location": "Siebkens Resort, Elkhart Lake, WI",
        "venue_name": "Siebkens Resort",
        "description": (
            "Annual motorcycle show at Siebkens during MotoAmerica weekend at "
            "Road America. Vintage and custom bikes on display."
        ),
        "categories": ["Community", "Sports"],
    },
    {
        "title": "MotoAmerica Superbikes & Vintage Motofest",
        "date": "2026-05-29",
        "end_date": "2026-05-31",
        "location": "Road America, Elkhart Lake, WI",
        "venue_name": "Road America",
        "description": (
            "MotoAmerica Superbike championship weekend featuring multi-class "
            "professional motorcycle road racing plus the Vintage Motofest. "
            "One of the season's biggest racing weekends."
        ),
        "categories": ["Sports", "Festival"],
    },
    {
        "title": "WeatherTech Chicago Region SCCA June Sprints",
        "date": "2026-06-05",
        "end_date": "2026-06-07",
        "location": "Road America, Elkhart Lake, WI",
        "venue_name": "Road America",
        "description": (
            "The longest-running SCCA national race in the U.S., featuring road "
            "racing across multiple classes at Road America."
        ),
        "categories": ["Sports"],
    },
    {
        "title": "XPEL IndyCar Grand Prix presented by AMR",
        "date": "2026-06-18",
        "end_date": "2026-06-21",
        "location": "Road America, Elkhart Lake, WI",
        "venue_name": "Road America",
        "description": (
            "NTT IndyCar Series race weekend at Road America's historic "
            "4-mile road course. The series' premier Wisconsin event."
        ),
        "categories": ["Sports", "Festival"],
    },
    {
        "title": "Cheese Capital Cup featuring Trans Am SpeedTour",
        "date": "2026-06-26",
        "end_date": "2026-06-28",
        "location": "Road America, Elkhart Lake, WI",
        "venue_name": "Road America",
        "description": (
            "Trans Am Series SpeedTour weekend featuring multi-class road racing "
            "at Road America. Includes the Cheese Capital Cup feature race."
        ),
        "categories": ["Sports"],
    },
    {
        "title": "Elkhart Lake Fireman's Fireworks & Annual Picnic",
        "date": "2026-07-03",
        "location": "Elkhart Lake Lakefront & Fireman's Park, Elkhart Lake, WI",
        "venue_name": "Elkhart Lake Lakefront & Fireman's Park",
        "description": (
            "Annual Independence Day weekend fireworks over the lake plus the "
            "fireman's picnic. Family-friendly community tradition."
        ),
        "categories": ["Community", "Family", "Festival", "Free"],
    },
    {
        "title": "Fireman's 4th of July Parade & Annual Picnic",
        "date": "2026-07-05",
        "location": "Elkhart Lake & Fireman's Park, Elkhart Lake, WI",
        "description": (
            "Independence Day parade through downtown Elkhart Lake followed by "
            "the annual fireman's picnic at Fireman's Park."
        ),
        "categories": ["Community", "Family", "Free"],
    },
    {
        "title": "Midwest Acoustic Music Festival",
        "date": "2026-07-11",
        "location": "Lake Street Cafe, Elkhart Lake, WI",
        "venue_name": "Lake Street Cafe",
        "description": (
            "Annual acoustic music festival featuring regional singer-songwriters "
            "and folk acts at Lake Street Cafe."
        ),
        "categories": ["Music", "Festival"],
    },
    {
        "title": "WeatherTech Vintage Weekend with Brian Redman",
        "date": "2026-07-16",
        "end_date": "2026-07-19",
        "location": "Road America, Elkhart Lake, WI",
        "venue_name": "Road America",
        "description": (
            "Vintage race weekend at Road America with renowned racer Brian "
            "Redman. Multiple classes of vintage racing plus paddock access."
        ),
        "categories": ["Sports", "Festival"],
    },
    {
        "title": "Vintage Concours d'Elegance & Parade - Racecars",
        "date": "2026-07-17",
        "location": "Downtown Elkhart Lake, WI",
        "venue_name": "Downtown Elkhart Lake",
        "description": (
            "Vintage racecar concours and parade through downtown Elkhart Lake "
            "during Vintage Weekend. Open to the public, free to attend."
        ),
        "categories": ["Sports", "Community", "Free"],
    },
    {
        "title": "Vintage Concours d'Elegance - Sportscars",
        "date": "2026-07-18",
        "location": "Downtown Elkhart Lake, WI",
        "venue_name": "Downtown Elkhart Lake",
        "description": (
            "Vintage sportscar concours in downtown Elkhart Lake. Classic cars "
            "on display throughout the village."
        ),
        "categories": ["Sports", "Community", "Free"],
    },
    {
        "title": "Motul Sportscar Endurance Grand Prix featuring IMSA",
        "date": "2026-07-30",
        "end_date": "2026-08-02",
        "location": "Road America, Elkhart Lake, WI",
        "venue_name": "Road America",
        "description": (
            "IMSA WeatherTech SportsCar Championship endurance race weekend at "
            "Road America. Multi-class sportscar racing."
        ),
        "categories": ["Sports", "Festival"],
    },
    {
        "title": "Downtown Night",
        "date": "2026-08-10",
        "location": "Downtown Elkhart Lake, WI",
        "venue_name": "Downtown Elkhart Lake",
        "description": (
            "Annual downtown street party in Elkhart Lake. Live music, food "
            "vendors, family activities."
        ),
        "categories": ["Community", "Festival", "Free"],
    },
    {
        "title": "Fanatec GT World Challenge America",
        "date": "2026-08-28",
        "end_date": "2026-08-30",
        "location": "Road America, Elkhart Lake, WI",
        "venue_name": "Road America",
        "description": (
            "GT World Challenge America Powered by AWS at Road America. "
            "Professional GT3 sportscar racing."
        ),
        "categories": ["Sports"],
    },
    {
        "title": "Art on Wheels Weekend with VSCDA",
        "date": "2026-09-18",
        "end_date": "2026-09-20",
        "location": "Road America, Elkhart Lake, WI",
        "venue_name": "Road America",
        "description": (
            "Vintage Sports Car Drivers Association weekend at Road America. "
            "Vintage racing and car show."
        ),
        "categories": ["Sports", "Community"],
    },
    {
        "title": "Elktoberfest",
        "date": "2026-09-19",
        "location": "Elkhart Lake, WI",
        "description": (
            "Annual Elkhart Lake Oktoberfest celebration. German food, beer, "
            "music, and family activities downtown."
        ),
        "categories": ["Community", "Festival", "Food & Drink"],
    },
    {
        "title": "SCCA National Championship Runoffs",
        "date": "2026-10-01",
        "end_date": "2026-10-04",
        "location": "Road America, Elkhart Lake, WI",
        "venue_name": "Road America",
        "description": (
            "SCCA's marquee national championship event at Road America. The "
            "biggest amateur road-racing event in North America."
        ),
        "categories": ["Sports", "Festival"],
    },
    {
        "title": "Old World Christmas Market",
        "date": "2026-12-04",
        "end_date": "2026-12-13",
        "location": "The Osthoff Resort, Elkhart Lake, WI",
        "venue_name": "The Osthoff Resort",
        "description": (
            "Authentic German-style Christmas market at The Osthoff Resort. "
            "European vendors, holiday food, traditional crafts, and festive "
            "decor over 10 days. A signature winter destination event."
        ),
        "categories": ["Festival", "Family", "Food & Drink"],
    },
]


def scrape_elkhart_recurring_locals() -> list:
    """Return hand-curated Elkhart Lake annual & signature events."""
    print("Loading Elkhart Lake recurring locals (curated)...")

    today_iso = datetime.now().strftime("%Y-%m-%d")
    out = []
    for ev in _ANNUAL_EVENTS:
        e = dict(ev)
        # Defaults
        e.setdefault("link", "https://www.elkhartlake.com/events/")
        e.setdefault("source", "Elkhart Lake Tourism")
        e.setdefault("source_url", "https://www.elkhartlake.com/")
        e.setdefault("lat", ELKHART_LAT)
        e.setdefault("lng", ELKHART_LNG)
        e["scraped_at"] = datetime.now().isoformat()
        # Drop past events (unless end_date is still future)
        eff = e.get("end_date") or e["date"]
        if eff >= today_iso:
            out.append(e)

    print(f"  [elkhart_recurring_locals] {len(out)} events")
    return out


if __name__ == "__main__":
    events = scrape_elkhart_recurring_locals()
    print()
    for e in sorted(events, key=lambda x: x["date"]):
        end = f" - {e['end_date']}" if e.get("end_date") else ""
        print(f"  {e['date']}{end} | {e['title'][:55]}")

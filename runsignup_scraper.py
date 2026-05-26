"""RunSignup race scraper — API-based (no scraping, no geocoding needed).

RunSignup is the dominant US race-registration platform with a free public
REST API. We query races within `radius` miles of a city's `zipcode`; the API
does the geo-filtering for us, so events are already city-scoped. Each city
wires this with its zip — reusable everywhere (Sun Valley = just a new zip).

API: https://runsignup.com/Rest/races  (no auth needed for race search)
"""
import requests
from datetime import datetime, date

API_URL = "https://runsignup.com/Rest/races"
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh) Chrome/124.0"}


def _us_to_iso(s):
    """MM/DD/YYYY -> YYYY-MM-DD. Returns None on failure."""
    if not s:
        return None
    try:
        return datetime.strptime(s.strip(), "%m/%d/%Y").strftime("%Y-%m-%d")
    except ValueError:
        return None


def scrape_runsignup_races(zipcode, radius=30, source_name="RunSignup",
                            default_lat=None, default_lng=None,
                            default_city=None, max_pages=3, timeout=20):
    today_iso = date.today().isoformat()
    events = []
    seen_ids = set()
    for page in range(1, max_pages + 1):
        try:
            r = requests.get(API_URL, headers=HEADERS, timeout=timeout, params={
                "format": "json",
                "results_per_page": 50,
                "page": page,
                "start_date": today_iso,
                "radius": radius,
                "zipcode": zipcode,
                "only_partner_races": "F",
            })
            data = r.json()
        except Exception as ex:
            print(f"  [runsignup] {source_name}: API error p{page}: {ex}")
            break

        races = data.get("races", [])
        if not races:
            break

        for wrap in races:
            race = wrap.get("race", {})
            rid = race.get("race_id")
            if rid in seen_ids:
                continue
            seen_ids.add(rid)
            # Skip non-public
            if race.get("is_draft_race") == "T" or race.get("is_private_race") == "T":
                continue
            start = _us_to_iso(race.get("next_date"))
            if not start:
                continue
            end = _us_to_iso(race.get("next_end_date")) or start
            if start < today_iso:
                continue
            addr = race.get("address") or {}
            city_txt = ", ".join(x for x in [addr.get("city"), addr.get("state")] if x)
            events.append({
                "title": race.get("name", "").strip(),
                "date": start,
                "end_date": end,
                "location": city_txt,
                "venue_name": addr.get("city") or "",
                "link": race.get("url") or race.get("external_race_url") or "",
                "source": source_name,
                "source_url": API_URL,
                "lat": default_lat or 0,
                "lng": default_lng or 0,
                "city": default_city or "",
                "categories": ["Running & Races"],
            })
        if len(races) < 50:
            break

    print(f"  [runsignup] {source_name}: {len(events)} future races (zip {zipcode}, {radius}mi)")
    return events


if __name__ == "__main__":
    evs = scrape_runsignup_races("83001", radius=30, source_name="RunSignup Jackson",
                                 default_lat=43.4799, default_lng=-110.7624,
                                 default_city="Jackson, WY")
    print(f"\n=== {len(evs)} races ===")
    for e in evs:
        print(f"  {e['date']} -> {e['end_date']} | {e['title'][:45]:45} | {e['location']}")

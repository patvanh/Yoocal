"""
RunSignup public API scraper for Park City + Heber Valley races.

RunSignup is the registration platform behind most local races in Utah
(Park City Trail Series, Triple Trail Challenge, Twisted Fork, Heber
Half, High Uinta Half, etc). Their public REST API is open — no auth.

API:
    GET https://runsignup.com/Rest/races
        ?format=json
        &events=T            (include sub-event details)
        &city=Park City
        &state=UT
        &start_date=YYYY-MM-DD
        &end_date=YYYY-MM-DD
        &results_per_page=50

Returns: {"races": [{"race": {...}}, ...]}

Each race has:
    race_id, name, url, description (HTML), address, next_date,
    timezone, events: [{event_id, name, start_time, end_time,
                        event_type, distance, ...}]

We expand each event into its own yoocal event because a single "race"
in RunSignup often contains multiple distinct sub-races on different
days (e.g., Park City Trail Series has 5K, 10K, Half on three dates).

Composite "Full Series" / "Short Half Series" events are skipped —
they're registration bundles, not separate things to attend.

Public entry points:
    scrape_runsignup_parkcity() -> list of event dicts
    scrape_runsignup_heber()    -> list of event dicts
"""

import requests
import re
from datetime import datetime, timedelta

API_URL = "https://runsignup.com/Rest/races"
SOURCE_NAME = "RunSignup"
SOURCE_URL = "https://runsignup.com"

# Heber-area cities to query — same approach as the old hardcoded heber_scraper
HEBER_CITIES = ["Heber City", "Midway", "Kamas", "Heber"]

# Park City + nearby (Deer Valley shows up under Park City)
PARK_CITY_CITIES = ["Park City"]


def scrape_runsignup_parkcity():
    """Fetch RunSignup races for Park City."""
    print("Scraping RunSignup for Park City races...")
    return _scrape_for_cities(PARK_CITY_CITIES, default_lat=40.6461, default_lng=-111.4980)


def scrape_runsignup_heber():
    """Fetch RunSignup races for Heber Valley + Midway + Kamas."""
    print("Scraping RunSignup for Heber Valley races...")
    return _scrape_for_cities(HEBER_CITIES, default_lat=40.5069, default_lng=-111.4133)


def _scrape_for_cities(cities, default_lat, default_lng):
    """Run a RunSignup API query for each city and parse all events."""
    all_events = []
    today_iso = datetime.now().strftime("%Y-%m-%d")
    end_date_iso = (datetime.now() + timedelta(days=300)).strftime("%Y-%m-%d")

    seen_race_event_keys = set()  # dedup across cities (some races appear under multiple)

    for city in cities:
        try:
            races = _fetch_races(city, today_iso, end_date_iso)
        except Exception as ex:
            print(f"  Error fetching {city}: {ex}")
            continue

        print(f"  {city}: {len(races)} races")

        for race_wrap in races:
            race = race_wrap.get("race", {})
            race_id = race.get("race_id")
            race_events = race.get("events") or []

            for ev in race_events:
                # Skip composite "series" entries — registration bundles, not separate events
                ev_name = (ev.get("name") or "").lower()
                if any(skip in ev_name for skip in [
                    "full race series",
                    "short half series",
                    "full series",
                    "short series",
                ]):
                    continue

                # Skip registration categories that aren't attendable public events
                if any(skip in ev_name for skip in [
                    "volunteer",          # Volunteer signups
                    "pacer",              # Pacer (Invite Only)
                    "virtual race",       # Remote/virtual entries
                    "invite only",
                ]):
                    continue

                # Skip team-size variants of the same event — keep just the first one
                # ("DASH - 2 Person", "DASH - 3 Person", etc. — same event, different team configs)
                if re.search(r"\b\d+\s*person\b", ev_name) or "family adventure" in ev_name:
                    continue

                # Skip ticket-type duplicates — "VIP Ticket", "Regular Ticket", "Premium Ticket" etc.
                if re.search(r"\b(vip|regular|general|premium|early\s*bird)\s*ticket\b", ev_name):
                    continue

                # The parent race itself is sometimes also listed as an event
                # (e.g. "Triple Trail Challenge" appears both as the umbrella AND
                # as an event with distance=None). Skip these umbrella entries.
                parent_race_name = (race.get("name") or "").lower().strip()
                if ev_name.strip() == parent_race_name and not ev.get("distance"):
                    continue

                parsed = _parse_event(race, ev, default_lat, default_lng)
                if not parsed:
                    continue
                if parsed["date"] < today_iso:
                    continue

                # Dedup key — race_id + event_id (avoids dupes when same race appears under 2 cities)
                key = (race_id, ev.get("event_id"))
                if key in seen_race_event_keys:
                    continue
                seen_race_event_keys.add(key)

                all_events.append(parsed)

    print(f"  Total: {len(all_events)} clean events from RunSignup")
    return all_events


def _fetch_races(city, start_date, end_date):
    """Single GET to the RunSignup races endpoint."""
    params = {
        "format": "json",
        "events": "T",
        "results_per_page": 50,
        "city": city,
        "state": "UT",
        "start_date": start_date,
        "end_date": end_date,
    }
    r = requests.get(
        API_URL,
        params=params,
        headers={"User-Agent": "Mozilla/5.0 yoocal-scraper"},
        timeout=20,
    )
    r.raise_for_status()
    return r.json().get("races", [])


def _parse_event(race, ev, default_lat, default_lng):
    """Convert one (race, event) pair to our standard schema."""
    try:
        # Title — combine race name + event distance/name for clarity
        race_name = (race.get("name") or "").strip()
        ev_name = (ev.get("name") or "").strip()

        # If the event name is just the distance (e.g., "5K", "10K"), prefix with race name
        # If it's a more descriptive name (e.g., "Mid Mountain 50K"), use it as-is
        if re.fullmatch(r"\d+\.?\d*\s*(K|Miles?|Mile|M)", ev_name, re.IGNORECASE) or \
           re.fullmatch(r"Half\s*Marathon", ev_name, re.IGNORECASE):
            title = f"{race_name}: {ev_name}"
        else:
            title = ev_name if ev_name else race_name

        if not title or len(title) < 3:
            return None

        # Date and time — start_time is "M/D/YYYY HH:MM" e.g. "9/5/2026 06:50"
        start_str = ev.get("start_time") or ""
        try:
            start_dt = datetime.strptime(start_str, "%m/%d/%Y %H:%M")
        except Exception:
            # Fallback to race-level next_date if event start_time isn't parseable
            try:
                next_date = race.get("next_date") or ""
                start_dt = datetime.strptime(next_date, "%m/%d/%Y")
            except Exception:
                return None

        date_iso = start_dt.strftime("%Y-%m-%d")
        # Only emit start_time if it's not midnight (00:00 means "no time set")
        start_time = None
        if not (start_dt.hour == 0 and start_dt.minute == 0):
            start_time = start_dt.strftime("%-I:%M %p")

        # End time
        end_time = None
        end_str = ev.get("end_time") or ""
        if end_str:
            try:
                end_dt = datetime.strptime(end_str, "%m/%d/%Y %H:%M")
                if not (end_dt.hour == 0 and end_dt.minute == 0) and start_time:
                    end_time = end_dt.strftime("%-I:%M %p")
            except Exception:
                pass

        # Description — strip HTML
        desc_html = race.get("description") or ""
        description = re.sub(r"<[^>]+>", " ", desc_html)
        description = re.sub(r"\s+", " ", description).strip()
        # Cap to something reasonable — race descriptions can be very long
        if len(description) > 600:
            description = description[:597] + "..."
        if not description:
            description = f"Race in {race.get('address',{}).get('city','Utah')}. See registration page for details."

        # Location
        addr = race.get("address") or {}
        addr_parts = []
        if addr.get("street") and addr["street"].lower() not in ("park city - all over the place",):
            addr_parts.append(addr["street"])
        if addr.get("city"):
            addr_parts.append(addr["city"])
        if addr.get("state"):
            addr_parts.append(addr["state"])
        location = ", ".join(addr_parts) if addr_parts else "Park City, UT"

        # Categories
        ev_type = (ev.get("event_type") or "").lower()
        categories = ["Running"]
        if "mountain_bike" in ev_type or "mtb" in ev_name.lower() or "bike" in ev_name.lower():
            categories = ["Cycling", "Outdoor"]
        elif "trail" in race_name.lower() or "trail" in ev_name.lower():
            categories = ["Running", "Outdoor"]

        # Link — race URL (registration page)
        link = race.get("external_race_url") or race.get("url") or SOURCE_URL

        event = {
            "title": title,
            "date": date_iso,
            "description": description,
            "location": location,
            "link": link,
            "source": SOURCE_NAME,
            "source_url": race.get("url") or SOURCE_URL,
            "lat": default_lat,
            "lng": default_lng,
            "categories": categories,
        }
        if start_time:
            event["start_time"] = start_time
        if end_time:
            event["end_time"] = end_time

        return event

    except Exception as ex:
        return None


if __name__ == "__main__":
    print("=" * 60)
    pc = scrape_runsignup_parkcity()
    print(f"\n{len(pc)} Park City events:")
    for e in pc:
        time_s = e.get("start_time", "(all day)")
        print(f"  {e['date']} {time_s:>9s} | {e['title'][:65]}")

    print()
    print("=" * 60)
    heber = scrape_runsignup_heber()
    print(f"\n{len(heber)} Heber events:")
    for e in heber:
        time_s = e.get("start_time", "(all day)")
        print(f"  {e['date']} {time_s:>9s} | {e['title'][:65]}")

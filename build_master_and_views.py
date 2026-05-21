"""Build events-all.json master file and per-city radius-filtered views.

Reads the 4 per-city events-*.json files, merges + dedupes globally,
writes events-all.json, then writes per-city views by radius filtering.

Architecture:
  events-all.json    ← all events nationwide, source of truth
  events.json        ← Park City filtered view (within 10mi of city center)
  events-heber.json  ← Heber filtered view (within 10mi)
  events-jackson.json ← Jackson filtered view (within 20mi)
  events-elkhartlake.json ← Elkhart filtered view (within 15mi)

Cross-region events (e.g. PC Marathon through Heber) naturally appear
on BOTH calendars without duplication.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone, timedelta
from pathlib import Path

MOUNTAIN = timezone(timedelta(hours=-6))

# City centers + radius (miles)
CITIES = {
    "park-city": {
        "lat": 40.6461, "lng": -111.4980, "radius_mi": 10,
        "out_file": "public/events.json",
    },
    "heber": {
        "lat": 40.5069, "lng": -111.4133, "radius_mi": 10,
        "out_file": "public/events-heber.json",
    },
    "jackson": {
        "lat": 43.4799, "lng": -110.7624, "radius_mi": 20,
        "out_file": "public/events-jackson.json",
    },
    "elkhart-lake": {
        "lat": 43.8330, "lng": -88.0426, "radius_mi": 15,
        "out_file": "public/events-elkhartlake.json",
    },
}

# Source files to read (current per-city files act as INPUT until we migrate scrapers)
INPUT_FILES = [
    "public/raw/events.json",
    "public/raw/events-heber.json",
    "public/raw/events-jackson.json",
    "public/raw/events-elkhartlake.json",
    "public/raw/events-egyptian.json",
]

MASTER_FILE = "public/events-all.json"


def haversine_miles(lat1, lng1, lat2, lng2):
    """Distance between two points in miles."""
    R = 3958.8
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lng2 - lng1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlmb/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


# Filler words that appear in aggregator titles but not venue-direct titles.
# Stripping these helps "Iris DeMent Tickets" and "An Evening with Iris DeMent"
# collapse to the same dedup key.
_TITLE_FILLERS = {
    "tickets", "ticket", "live", "presents", "an", "a", "the",
    "evening", "with", "feat", "featuring", "vs", "and",
    "concert", "show", "performance", "performs",
    "park", "city",  # location words also strip
}

def _normalize_title(title: str) -> str:
    """Aggressive normalization: lowercase, strip punctuation + filler words."""
    import re as _re
    if not title:
        return ""
    t = title.lower()
    t = _re.sub(r"[^a-z0-9 ]+", " ", t)  # punctuation -> space
    tokens = [w for w in t.split() if w and w not in _TITLE_FILLERS]
    return " ".join(tokens)


def event_key(e: dict) -> tuple:
    """Unique key for global dedup: (normalized_title, date, start_time).

    Title normalization is aggressive — drops filler words ("tickets",
    "an evening with", "live", etc.) so aggregator titles collapse to the
    same key as venue-direct titles for the same show.
    """
    title = _normalize_title(e.get("title") or "")
    date = (e.get("date") or "")[:10]
    start = (e.get("start_time") or "").strip()
    return (title, date, start)


def merge_events(records: list[dict]) -> dict:
    """When multiple records dedupe to the same key, pick the best fields."""
    if len(records) == 1:
        return records[0]
    
    # Sort by source priority (lower = better).
    # Default for unknown sources is now Tier 2 (3), not below Tier 4 — a new
    # source we haven't classified is almost always a venue/organizer worth
    # trusting more than third-party aggregators.
    SOURCE_PRIORITY = {
        # Tier 1: verified venue or primary organizer — authoritative for their events
        "Oakley City": 1, "Eccles Center": 1, "Park City Institute": 1,
        "Deer Valley Resort": 1, "Park City Mountain": 1,
        "Deer Valley Music Festival": 1, "Grand Teton Music Festival": 1,
        "The Grand Teton Music Festival": 1,  # legacy alias
        "The Cloudveil": 1, "The Osthoff Resort": 1, "Siebkens Resort": 1,
        "Road America": 1, "National Museum of Wildlife Art": 1,
        "Center for the Arts Jackson Hole": 1, "Park City Opera": 1,
        "Park City Song Summit": 1, "Park City Farmers Market": 1,
        "Mountain Trails Foundation": 1, "Village of Elkhart Lake": 1,
        "Egyptian Theatre": 1,

        # Tier 2: trusted aggregator, tourism board, or local newspaper
        "The Park Record": 2, "Park City Annual Events": 2,
        "Visit Park City": 2, "Visit Park City (sitemap)": 2,
        "Mountain Town Music": 2, "Heber Valley Tourism": 2,
        "Jackson Hole Chamber of Commerce": 2, "Elkhart Lake Tourism": 2,
        "RunSignup": 2, "Salt Lake Running Co": 2,
        "Park City Gallery Association": 2,

        # Tier 3: community calendar or non-canonical local source
        "KPCW Community Calendar": 3, "Heber Valley Life": 3,

        # Tier 4: third-party aggregator (never overrides Tier 1-3 fields)
        "Google Events": 4, "Eventbrite": 4, "Bandsintown": 4,
        "EventTicketsCenter": 4,
    }

    DEFAULT_PRIORITY = 3  # unknown source -> assume community calendar tier

    records.sort(key=lambda r: SOURCE_PRIORITY.get(r.get("source", ""), DEFAULT_PRIORITY))
    
    base = dict(records[0])  # highest-priority record wins as base
    
    # Fill in missing fields from lower-priority records
    for r in records[1:]:
        for key in ["description", "start_time", "end_time", "address",
                    "venue_name", "image_url", "link", "lat", "lng"]:
            if not base.get(key) and r.get(key):
                base[key] = r[key]
        # Merge categories
        cats = set(base.get("categories") or [])
        cats.update(r.get("categories") or [])
        if cats:
            base["categories"] = sorted(cats)
        # Track all sources
        srcs = set(base.get("_all_sources") or [base.get("source", "")])
        srcs.add(r.get("source", ""))
        srcs.discard("")
        base["_all_sources"] = sorted(srcs)
    
    return base


def main():
    today_iso = datetime.now(MOUNTAIN).strftime("%Y-%m-%d")
    print(f"Building master + city views — {today_iso}")
    print("=" * 60)
    
    # Step 1: Read all input files, merge into a big list
    all_events = []
    for path in INPUT_FILES:
        try:
            d = json.load(open(path))
            events = d.get("events", d) if isinstance(d, dict) else d
            print(f"  Loaded {len(events):5d} from {path}")
            all_events.extend(events)
        except FileNotFoundError:
            print(f"  SKIP: {path} not found")
    
    print(f"\nTotal records (before dedup): {len(all_events)}")
    
    # Step 2: Global dedup
    by_key = {}
    for e in all_events:
        k = event_key(e)
        by_key.setdefault(k, []).append(e)
    
    deduped = [merge_events(group) for group in by_key.values()]
    print(f"Deduped records: {len(deduped)}")
    print(f"Duplicates merged: {len(all_events) - len(deduped)}")
    
    # Step 3: Filter past events
    future = [e for e in deduped if (e.get("date") or "")[:10] >= today_iso]
    print(f"Future events: {len(future)}")
    
    # Step 4: Write master file
    master = {
        "version": 2,
        "generated_at": datetime.now(MOUNTAIN).isoformat(),
        "today": today_iso,
        "event_count": len(future),
        "events": future,
    }
    Path(MASTER_FILE).parent.mkdir(parents=True, exist_ok=True)
    json.dump(master, open(MASTER_FILE, "w"), indent=2)
    print(f"\n[master] wrote {len(future)} events to {MASTER_FILE}")
    
    # Step 5: Build per-city views by radius
    print(f"\n{'City':<15} {'In radius':>10} {'Has geo':>10}")
    print(f"{'-'*15} {'-'*10} {'-'*10}")
    for city, cfg in CITIES.items():
        in_radius = []
        has_geo = 0
        for e in future:
            lat = e.get("lat")
            lng = e.get("lng")
            # Source-based geo fallback for events missing coords
            if lat is None or lng is None:
                source = (e.get("source") or "").lower()
                if "elkhart" in source or "osthoff" in source or "road america" in source or "siebkens" in source:
                    lat, lng = 43.8330, -88.0426  # Elkhart Lake center
                elif "heber" in source or "wasatch" in source or "midway" in source:
                    lat, lng = 40.5069, -111.4133  # Heber center
                elif "jackson" in source or "teton" in source or "cloudveil" in source:
                    lat, lng = 43.4799, -110.7624  # Jackson center
                elif "park city" in source or "park record" in source or "mountain town" in source or "deer valley" in source:
                    lat, lng = 40.6461, -111.4980  # PC center
                else:
                    continue
            has_geo += 1
            try:
                dist = haversine_miles(cfg["lat"], cfg["lng"], float(lat), float(lng))
            except (ValueError, TypeError):
                continue
            if dist <= cfg["radius_mi"]:
                # Add a distance hint for frontend
                e_copy = dict(e)
                e_copy["_distance_mi"] = round(dist, 1)
                in_radius.append(e_copy)
        
        # Write per-city view
        out = {
            "version": 2,
            "city": city,
            "city_center": {"lat": cfg["lat"], "lng": cfg["lng"]},
            "radius_mi": cfg["radius_mi"],
            "generated_at": datetime.now(MOUNTAIN).isoformat(),
            "today": today_iso,
            "event_count": len(in_radius),
            "events": in_radius,
        }
        json.dump(out, open(cfg["out_file"], "w"), indent=2)
        print(f"{city:<15} {len(in_radius):>10} {has_geo:>10}")
    
    print(f"\nDone!")


if __name__ == "__main__":
    main()

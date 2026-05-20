"""Apply human-curated event overrides to events JSON files.

Solves the problem where the scraper has bad/incomplete data that we've
manually corrected — and the next scrape overwrites our corrections.

This module loads `event_overrides.json`, matches events by title/date pattern,
and applies the override fields. It runs as part of the daily pipeline AFTER
the scraper saves its output, before audit/classify.

Override file format (event_overrides.json):
{
  "overrides": [
    {
      "_id": "oakley-rodeo-2026",                  // for log readability
      "city": "heber",                              // which events JSON to touch
      "match": {
        "title_contains": "oakley rodeo",          // case-insensitive substring
        "date_in": ["2026-07-01", "2026-07-02"]   // OR date_range, OR not specified
      },
      "set": {
        "title": "Oakley PRCA Rodeo",
        "start_time": "7:30 PM",
        "end_time": "10:00 PM",
        "description": "...",
        "venue_name": "Oakley City Recreational Complex",
        ...
      },
      "drop_if_unmatched": false   // optional: drop events that match but were originally elsewhere
    },
    {
      "_id": "oakley-bull-2026",
      "city": "heber",
      "match": {
        "title_contains": "oakley xtreme bulls",
        "date_eq": "2026-07-06"
      },
      "set": { ... }
    },
    {
      "_id": "oakley-add-pickleball",
      "city": "heber",
      "create": {                                   // create a new event if no match
        "title": "3rd Annual Oakley Pickleball Tournament",
        "date": "2026-06-26",
        ...
      }
    },
    {
      "_id": "remove-bad-xtreme-bulls",
      "city": "heber",
      "match": {
        "title_contains": "xtreme bulls",
        "start_time_eq": "10:30 PM"
      },
      "remove": true                                // delete matching records
    }
  ]
}

Usage:
  python event_overrides.py            # apply all overrides
  python event_overrides.py heber      # apply to heber only
"""
from __future__ import annotations

import json
import sys
import re
from pathlib import Path
from datetime import datetime


CITY_FILES = {
    "park-city": "public/events.json",
    "elkhart-lake": "public/events-elkhartlake.json",
    "heber": "public/events-heber.json",
    "jackson": "public/events-jackson.json",
}

OVERRIDE_FILE = "event_overrides.json"


def _match(event: dict, match_spec: dict) -> bool:
    """Check if an event matches the spec."""
    title = (event.get("title") or "").lower()
    date = (event.get("date") or "")[:10]
    start = event.get("start_time") or ""
    end = event.get("end_time") or ""
    source = (event.get("source") or "").lower()

    if "title_contains" in match_spec:
        if match_spec["title_contains"].lower() not in title:
            return False

    if "title_eq" in match_spec:
        if title != match_spec["title_eq"].lower():
            return False

    if "date_eq" in match_spec:
        if date != match_spec["date_eq"]:
            return False

    if "date_in" in match_spec:
        if date not in match_spec["date_in"]:
            return False

    if "date_range" in match_spec:
        rng = match_spec["date_range"]
        if not (rng[0] <= date <= rng[1]):
            return False

    if "start_time_eq" in match_spec:
        if start != match_spec["start_time_eq"]:
            return False

    if "source_contains" in match_spec:
        if match_spec["source_contains"].lower() not in source:
            return False

    return True


def apply_overrides_to_city(city_key: str, events: list, overrides: list) -> dict:
    """Apply all overrides for one city. Returns a stats dict."""
    stats = {"matched": 0, "created": 0, "removed": 0, "log": []}

    # Process in order so removes happen first, then updates, then creates
    city_overrides = [o for o in overrides if o.get("city") == city_key]

    # 1. Removes
    new_events = []
    for e in events:
        keep = True
        for ov in city_overrides:
            if not ov.get("remove"):
                continue
            if _match(e, ov.get("match") or {}):
                stats["removed"] += 1
                stats["log"].append(f"REMOVED [{ov.get('_id', 'unnamed')}]: {(e.get('title') or '')[:50]}")
                keep = False
                break
        if keep:
            new_events.append(e)
    events[:] = new_events

    # 2. Set (modify existing)
    for e in events:
        for ov in city_overrides:
            if ov.get("remove") or ov.get("create"):
                continue
            if not ov.get("set"):
                continue
            if _match(e, ov.get("match") or {}):
                changes = []
                for key, val in ov["set"].items():
                    if e.get(key) != val:
                        changes.append(key)
                    e[key] = val
                if changes:
                    stats["matched"] += 1
                    stats["log"].append(
                        f"SET [{ov.get('_id', 'unnamed')}] {(e.get('title') or '')[:40]} "
                        f"({e.get('date')}): {', '.join(changes)}"
                    )

    # 3. Creates (add new records)
    existing_ids = {(e.get("title", "").lower(), e.get("date")) for e in events}
    for ov in city_overrides:
        if not ov.get("create"):
            continue
        new_event = dict(ov["create"])
        key = (new_event.get("title", "").lower(), new_event.get("date"))
        if key in existing_ids:
            stats["log"].append(
                f"SKIP [{ov.get('_id', 'unnamed')}] (duplicate): {new_event.get('title')}"
            )
            continue
        new_event.setdefault("_added_by", "event_overrides.py")
        events.append(new_event)
        existing_ids.add(key)
        stats["created"] += 1
        stats["log"].append(f"CREATED [{ov.get('_id', 'unnamed')}]: {new_event.get('title')[:50]}")

    return stats


def main(target_city: str | None = None):
    if not Path(OVERRIDE_FILE).exists():
        print(f"No {OVERRIDE_FILE} found. Nothing to do.")
        return

    overrides_data = json.load(open(OVERRIDE_FILE))
    overrides = overrides_data.get("overrides") or []

    print(f"Event Overrides — {datetime.now().isoformat()}")
    print(f"  Loaded {len(overrides)} override rules from {OVERRIDE_FILE}")
    print()

    cities = [target_city] if target_city else list(CITY_FILES.keys())

    total = {"matched": 0, "created": 0, "removed": 0}

    for city in cities:
        if city not in CITY_FILES:
            print(f"  unknown city: {city}")
            continue

        path = CITY_FILES[city]
        try:
            d = json.load(open(path))
        except FileNotFoundError:
            print(f"  {city}: {path} not found")
            continue

        events = d.get("events", d) if isinstance(d, dict) else d
        before = len(events)
        stats = apply_overrides_to_city(city, events, overrides)
        after = len(events)

        if stats["matched"] or stats["created"] or stats["removed"]:
            print(f"=== {city} ===")
            print(f"  before: {before}  after: {after}")
            print(
                f"  modified: {stats['matched']}  created: {stats['created']}  "
                f"removed: {stats['removed']}"
            )
            for line in stats["log"][:15]:
                print(f"    {line}")
            if len(stats["log"]) > 15:
                print(f"    ... and {len(stats['log']) - 15} more")
            print()

        # Save changes back
        if isinstance(d, dict) and "events" in d:
            d["events"] = events
            json.dump(d, open(path, "w"), indent=2)

        total["matched"] += stats["matched"]
        total["created"] += stats["created"]
        total["removed"] += stats["removed"]

    print(f"Total — modified: {total['matched']}, created: {total['created']}, removed: {total['removed']}")


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else None
    main(target)
